"""Governance Gateway — aiohttp Sidecar proxy with policy enforcement.

Usage:
    python -m src.main
    # Starts on port 9000. Point your Agent client at localhost:9000/v1/intercept.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from aiohttp import web, ClientSession, ClientTimeout

from .models import InterceptRequest, InterceptResponse, Verdict
from .policy import PolicyEngine, Rule
from .storage import Storage

logger = logging.getLogger(__name__)

# ── configurable constants ──────────────────────────────────────────
INTERCEPT_TIMEOUT = 0.5       # seconds — if policy eval exceeds this, auto-ALLOW
CIRCUIT_BREAKER_LIMIT = 10    # consecutive ESCALATE without resolution → ALLOW
AGENT_BACKEND_URL = "http://localhost:8000"   # upstream Agent (for proxy mode)

# ── global state ────────────────────────────────────────────────────
start_time = time.time()
escalate_count_since_resolve = 0
last_escalate_time = 0.0
policy_engine: Optional[PolicyEngine] = None
storage: Optional[Storage] = None


def _uptime() -> float:
    return time.time() - start_time


async def resolve_policy() -> Rule:
    """Wait for policy engine to evaluate. Returns ALLOW-default if timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(policy_engine.evaluate, "...pending...", "POST"),
            timeout=INTERCEPT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return None


def _is_dangerous(path: str, method: str) -> bool:
    """Heuristic: operations that modify state are dangerous when uncertain."""
    dangerous_prefixes = ("/api/delete", "/api/admin", "/api/config", "/api/model")
    dangerous_methods = ("DELETE", "POST", "PUT", "PATCH")
    if method.upper() in dangerous_methods:
        for prefix in dangerous_prefixes:
            if path.startswith(prefix):
                return True
    return False


# ── handlers ────────────────────────────────────────────────────────

async def intercept_handler(request: web.Request) -> web.Response:
    global escalate_count_since_resolve

    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": "invalid JSON"}, status=400
        )

    try:
        req = InterceptRequest(**data)
    except Exception:
        return web.json_response(
            {"error": "invalid request body"}, status=422
        )

    # 1. evaluate policy with timeout guard
    try:
        rule = await asyncio.wait_for(
            asyncio.to_thread(policy_engine.evaluate, req.path, req.method),
            timeout=INTERCEPT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        # timeout → fail-closed for dangerous operations, escalate for others
        # (v0.1.0 had fail-open: auto-ALLOW. CRITIQUE_V2.md #1 fixed this.)
        if _is_dangerous(req.path, req.method):
            verdict = Verdict.DENY
            reason = "策略评估超时，高风险操作默认拒绝 (fail-closed)"
        else:
            verdict = Verdict.ESCALATE
            reason = "策略评估超时，升级人工审批 (fail-closed)"
        matched_rule = None
        logger.warning("policy evaluation timed out for %s %s → %s", req.method, req.path, verdict.value)
    else:
        # 2. determine verdict from matched rule
        if rule is None:
            verdict = Verdict.ALLOW
            reason = "无匹配策略，默认放行"
            matched_rule = None
        else:
            matched_rule = rule.name
            if rule.action == "DENY":
                verdict = Verdict.DENY
                reason = rule.reason or f"匹配规则 '{rule.name}' → 拦截"
            elif rule.action == "ESCALATE":
                global last_escalate_time
                now = time.time()
                if now - last_escalate_time > 300:
                    escalate_count_since_resolve = 1  # fresh burst, reset counter
                else:
                    escalate_count_since_resolve += 1
                last_escalate_time = now
                if escalate_count_since_resolve >= CIRCUIT_BREAKER_LIMIT:
                    verdict = Verdict.ALLOW
                    reason = f"连续 {escalate_count_since_resolve} 次升级未获审批，熔断放行"
                    escalate_count_since_resolve = 0
                else:
                    verdict = Verdict.ESCALATE
                    reason = rule.reason or f"匹配规则 '{rule.name}' → 升级人工审批"
            else:
                verdict = Verdict.ALLOW
                reason = rule.reason or f"匹配规则 '{rule.name}' → 放行"
                # successful ALLOW = request resolved → reset circuit breaker
                escalate_count_since_resolve = 0
                last_escalate_time = 0.0

    # 3. persist decision
    decision = {
        "id": str(uuid.uuid4()),
        "verdict": verdict.value,
        "reason": reason,
        "matched_rule": matched_rule,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": req.path,
        "method": req.method,
        "agent_id": req.agent_id,
    }
    storage.save(decision)

    # 4. if ALLOW and proxy mode → forward to upstream Agent
    response_body = None
    if verdict == Verdict.ALLOW and AGENT_BACKEND_URL:
        response_body = await _proxy_forward(req)

    # 5. build response
    resp = InterceptResponse(
        verdict=verdict,
        reason=reason,
        decision_id=decision["id"],
        matched_rule=matched_rule,
    )

    if verdict == Verdict.DENY:
        return web.json_response(resp.model_dump(mode="json"), status=403)
    elif verdict == Verdict.ESCALATE:
        return web.json_response(resp.model_dump(mode="json"), status=202)
    else:
        result = resp.model_dump(mode="json")
        if response_body:
            result["upstream_response"] = response_body
        return web.json_response(result, status=200)


async def _proxy_forward(req: InterceptRequest) -> Optional[dict]:
    """Forward the request to the upstream Agent backend."""
    try:
        async with ClientSession(timeout=ClientTimeout(total=0.5, connect=0.3)) as session:
            async with session.request(
                method=req.method,
                url=f"{AGENT_BACKEND_URL}{req.path}",
                headers={k: v for k, v in req.headers.items() if k.lower() != "host"},
                json=json.loads(req.body) if req.body else None,
            ) as resp:
                text = await resp.text()
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"status": resp.status, "body": text[:1000]}
    except Exception as e:
        logger.warning("proxy forward failed: %s", e)
        return None


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "version": "0.1.0",
        "uptime_seconds": round(_uptime(), 2),
        "decisions_total": storage.count(),
    })


async def decisions_handler(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", 50))
    decisions = storage.get_recent(limit)
    return web.json_response({"total": len(decisions), "decisions": decisions})


# ── app factory ─────────────────────────────────────────────────────

def create_app() -> web.Application:
    global policy_engine, storage, escalate_count_since_resolve, last_escalate_time
    policy_engine = PolicyEngine()
    storage = Storage()
    escalate_count_since_resolve = 0
    last_escalate_time = 0.0

    app = web.Application()
    app.router.add_post("/v1/intercept", intercept_handler)
    app.router.add_get("/v1/health", health_handler)
    app.router.add_get("/v1/decisions", decisions_handler)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    logger.info("governance-gateway v0.1.0 starting on :9000")
    web.run_app(app, port=9000)
