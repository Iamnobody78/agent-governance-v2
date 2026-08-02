"""Governance Gateway — aiohttp Sidecar proxy with policy enforcement.

Usage:
    python -m src.main
    # Starts on port 9000. Point your Agent client at localhost:9000/v1/intercept.
"""

import asyncio
import json
import logging
import posixpath
import time
import uuid
from typing import Optional

from aiohttp import web, ClientSession, ClientTimeout

from .models import InterceptRequest, InterceptResponse, DecisionRecord, Verdict
from .policy import PolicyEngine, Rule
from .storage import Storage

logger = logging.getLogger(__name__)

# ── configurable constants ──────────────────────────────────────────
INTERCEPT_TIMEOUT = 0.5       # seconds — if policy eval exceeds this, fail-closed
CIRCUIT_BREAKER_LIMIT = 10    # consecutive ESCALATE without resolution → DENY (fail-closed)
AGENT_BACKEND_URL = "http://localhost:8000"   # upstream Agent (for proxy mode)

# Shared heuristic constants — exported for policy_probe.py (single source of truth)
DANGEROUS_PREFIXES = ("/api/delete", "/api/admin", "/api/config", "/api/model")
DANGEROUS_METHODS = ("DELETE", "POST", "PUT", "PATCH")

# Only these headers are forwarded to the upstream backend (never Authorization)
FORWARD_HEADER_WHITELIST = ("content-type", "accept", "user-agent", "x-agent-id")

# ── global state ────────────────────────────────────────────────────
start_time = time.time()
escalate_count_since_resolve = 0
last_escalate_time = 0.0
_escalate_lock: asyncio.Lock = None  # guards escalate_count_since_resolve / last_escalate_time
policy_engine: Optional[PolicyEngine] = None
storage: Optional[Storage] = None


def _uptime() -> float:
    return time.time() - start_time


def _is_dangerous(path: str, method: str) -> bool:
    """Heuristic: operations that modify state are dangerous when uncertain.

    Defense layers (v0.2.0 security hardening, AUDIT-0005):
      1. normpath normalizes '/api/delete/../admin/exec' → '/api/admin/exec',
         killing path-traversal bypasses.
      2. Boundary matching: '/api/delete-evil' does NOT match prefix '/api/delete'.
      3. Segment-level fallback: '/api/v1/delete' (path variant) hits the
         dangerous tail segment 'delete' even without an exact prefix match.
    """
    if method.upper() not in DANGEROUS_METHODS:
        return False
    normalized = posixpath.normpath(path.split("?", 1)[0])
    # 1) exact/prefix match with boundary
    for prefix in DANGEROUS_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    # 2) segment-level fallback: any dangerous tail segment anywhere in path
    dangerous_tails = {p.rsplit("/", 1)[-1] for p in DANGEROUS_PREFIXES}
    segments = normalized.split("/")
    if any(seg in dangerous_tails for seg in segments):
        return True
    return False


# ── handlers ────────────────────────────────────────────────────────

async def intercept_handler(request: web.Request) -> web.Response:
    global escalate_count_since_resolve, last_escalate_time

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
                now = time.time()
                async with _escalate_lock:
                    if now - last_escalate_time > 300:
                        escalate_count_since_resolve = 1  # fresh burst, reset counter
                    else:
                        escalate_count_since_resolve += 1
                    last_escalate_time = now
                    if escalate_count_since_resolve >= CIRCUIT_BREAKER_LIMIT:
                        # v0.2.0 (AUDIT-0005): breaker trips to DENY, NOT ALLOW.
                        # A gateway that lost judgment must refuse, not bypass itself.
                        verdict = Verdict.DENY
                        reason = f"连续 {escalate_count_since_resolve} 次升级未获审批，熔断拒绝 (fail-closed)"
                        escalate_count_since_resolve = 0
                    else:
                        verdict = Verdict.ESCALATE
                        reason = rule.reason or f"匹配规则 '{rule.name}' → 升级人工审批"
            else:
                verdict = Verdict.ALLOW
                reason = rule.reason or f"匹配规则 '{rule.name}' → 放行"
                # successful ALLOW = request resolved → reset circuit breaker
                async with _escalate_lock:
                    escalate_count_since_resolve = 0
                    last_escalate_time = 0.0

    # 3. persist decision (strong-typed model, serialized at DB edge)
    decision = DecisionRecord(
        id=str(uuid.uuid4()),
        verdict=verdict,
        reason=reason,
        matched_rule=matched_rule,
        path=req.path,
        method=req.method,
        agent_id=req.agent_id,
    )
    storage.save(decision.model_dump(mode="json"))

    # 4. if ALLOW and proxy mode → forward to upstream Agent
    response_body = None
    if verdict == Verdict.ALLOW and AGENT_BACKEND_URL:
        response_body = await _proxy_forward(req)

    # 5. build response
    resp = InterceptResponse(
        verdict=verdict,
        reason=reason,
        decision_id=decision.id,
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
    """Forward the request to the upstream Agent backend.

    v0.2.0 (AUDIT-0005): only whitelisted headers are forwarded.
    Authorization / cookies are NEVER proxied upstream.
    """
    try:
        async with ClientSession(timeout=ClientTimeout(total=0.5, connect=0.3)) as session:
            # body may be a parsed dict (InterceptRequest.body) or raw JSON str
            body = req.body
            if isinstance(body, str) and body.strip():
                body = json.loads(body)
            async with session.request(
                method=req.method,
                url=f"{AGENT_BACKEND_URL}{req.path}",
                headers={
                    k: v for k, v in req.headers.items()
                    if k.lower() in FORWARD_HEADER_WHITELIST
                },
                json=body,
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
        "version": "0.2.0",
        "uptime_seconds": round(_uptime(), 2),
        "decisions_total": storage.count(),
    })


async def decisions_handler(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", 50))
    decisions = storage.get_recent(limit)
    return web.json_response({"total": len(decisions), "decisions": decisions})


# ── app factory ─────────────────────────────────────────────────────

def create_app() -> web.Application:
    global policy_engine, storage, escalate_count_since_resolve, last_escalate_time, _escalate_lock
    policy_engine = PolicyEngine()
    storage = Storage()
    escalate_count_since_resolve = 0
    last_escalate_time = 0.0
    _escalate_lock = asyncio.Lock()

    app = web.Application()
    app.router.add_post("/v1/intercept", intercept_handler)
    app.router.add_get("/v1/health", health_handler)
    app.router.add_get("/v1/decisions", decisions_handler)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    logger.info("governance-gateway v0.2.0 starting on :9000")
    web.run_app(app, port=9000)
