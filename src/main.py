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
from typing import Optional

from aiohttp import web, ClientSession, ClientTimeout

from .models import InterceptRequest, InterceptResponse, DecisionRecord, Verdict
from .lethality import lethality_for_tool
from .policy import PolicyEngine, Rule, _json_extract
from .storage import Storage

logger = logging.getLogger(__name__)

# ── configurable constants ──────────────────────────────────────────
INTERCEPT_TIMEOUT = 0.5       # seconds — if policy eval exceeds this, fail-closed
CIRCUIT_BREAKER_LIMIT = 10    # consecutive ESCALATE without resolution → DENY (fail-closed)
CIRCUIT_COOLDOWN_SECONDS = 30.0  # breaker trip cooldown window (DEBT-0001)
AGENT_BACKEND_URL = "http://localhost:8000"   # upstream Agent (for proxy mode)
SHUTDOWN_FLUSH_TIMEOUT = 8  # DEBT-0015: independent cap for shutdown flush; must stay < shutdown_timeout=10
MAX_TRACE_ID_LEN = 128  # TASK-REAL-011.1 (Critic-Security): trace 头值长度上限（超长视为缺失）

# Shared heuristic constants — single source of truth moved to src/danger.py (DEBT-0002)
from .danger import DANGEROUS_PREFIXES, DANGEROUS_METHODS, is_dangerous as _is_dangerous

# TASK-REAL-009 (A-phase): semantic bypass hook — external LLM-Judge, opt-in.
from .semantic_hook import extract_prompt, is_enabled as semantic_hook_enabled, semantic_hook

# Only these headers are forwarded to the upstream backend (never Authorization)
FORWARD_HEADER_WHITELIST = ("content-type", "accept", "user-agent", "x-agent-id")

# ── global state ────────────────────────────────────────────────────
start_time = time.time()
escalate_count_since_resolve = 0
last_escalate_time = 0.0
breaker_tripped_until = 0.0  # DEBT-0001: deny-all until this timestamp after trip
_escalate_lock: asyncio.Lock = None  # guards escalate_count_since_resolve / last_escalate_time
policy_engine: Optional[PolicyEngine] = None
storage: Optional[Storage] = None


def _uptime() -> float:
    return time.time() - start_time


# ── handlers ────────────────────────────────────────────────────────

def _trace_context(headers) -> tuple:
    """TASK-REAL-011 (C 阶段): 提取/生成 Trace 因果上下文。

    返回 (trace_id, parent_span_id):
      - trace_id:       X-Trace-ID 头; 缺失 → 新 UUID (本请求开启新调用链)。
      - parent_span_id: X-Parent-Span-ID 头; 缺失 → None (链根节点, 递归 CTE
                        锚点)。当前请求自身的 span_id == decision.id (判定后
                        生成), 通过响应头 X-Span-ID 回传, 下游请求携带
                        X-Parent-Span-ID 指向它即形成因果链。
    设计裁决: 用户确认表"若无 X-Parent-Span-ID 则生成"落地为"生成新链根
    语义"——随机占位 UUID 无法被 CTE 锚定 (parent 必须指向真实父决策 id),
    None 才是唯一自洽的根标记 (详见 docs/trace_report.md §3)。
    """
    trace_id = headers.get("X-Trace-ID") or str(uuid.uuid4())
    parent_span_id = headers.get("X-Parent-Span-ID") or None
    # TASK-REAL-011.1 (Critic-Security): 超长头值拒绝持久化 — 防止索引膨胀/
    # 存储滥用。>MAX_TRACE_ID_LEN 视为缺失 (fail-safe): trace_id → 新链根,
    # parent_span_id → None (根锚点)。截断会破坏链引用, 拒绝/降级为缺失是
    # 唯一不引入悬空引用的语义。
    if len(trace_id) > MAX_TRACE_ID_LEN:
        trace_id = str(uuid.uuid4())
    if parent_span_id is not None and len(parent_span_id) > MAX_TRACE_ID_LEN:
        parent_span_id = None
    return trace_id, parent_span_id


async def intercept_handler(request: web.Request) -> web.Response:
    global escalate_count_since_resolve, last_escalate_time, breaker_tripped_until

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

    # TASK-REAL-011 (C): 入口处提取 Trace 上下文 — 贯穿本请求全部决策分支
    trace_id, parent_span_id = _trace_context(request.headers)

    # 0. hot-reload policies if YAML changed (DEBT-0005)
    await asyncio.to_thread(policy_engine.maybe_reload)
    # 1. evaluate policy with timeout guard
    #    TASK-REAL-010 (B): req.body 传入 — json_path 条件规则检查请求体 JSON
    try:
        rule = await asyncio.wait_for(
            asyncio.to_thread(policy_engine.evaluate, req.path, req.method, req.body),
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
                    if now < breaker_tripped_until:
                        # DEBT-0001: cooldown window — deny everything until cooldown expires
                        verdict = Verdict.DENY
                        reason = f"熔断冷却中 ({breaker_tripped_until - now:.0f}s 后恢复)，拒绝 (fail-closed)"
                    else:
                        escalate_count_since_resolve += 1
                        last_escalate_time = now
                        if escalate_count_since_resolve >= CIRCUIT_BREAKER_LIMIT:
                            # v0.2.0 (AUDIT-0005): breaker trips to DENY, NOT ALLOW.
                            # DEBT-0001: trip starts a cooldown window; counter resets but
                            # the cooldown prevents immediate re-accumulation.
                            breaker_tripped_until = now + CIRCUIT_COOLDOWN_SECONDS
                            escalate_count_since_resolve = 0
                            await asyncio.to_thread(
                                storage.save_breaker_state,
                                escalate_count_since_resolve,
                                last_escalate_time,
                                breaker_tripped_until,
                            )
                            verdict = Verdict.DENY
                            reason = f"连续 {CIRCUIT_BREAKER_LIMIT} 次升级未获审批，熔断拒绝 (fail-closed)"
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
                    breaker_tripped_until = 0.0
                await asyncio.to_thread(
                    storage.save_breaker_state,
                    escalate_count_since_resolve,
                    last_escalate_time,
                    breaker_tripped_until,
                )

    # 2.5 semantic bypass hook (TASK-REAL-009 / A-phase): the static verdict may
    # be upgraded to ESCALATE by the external LLM-Judge — NEVER downgraded
    # (DENY stays final). Fail-soft: judge down/timeout -> verdict unchanged.
    if verdict != Verdict.DENY and semantic_hook_enabled():
        _prompt = extract_prompt(req.body)
        _semantic = await semantic_hook(_prompt)
        if _semantic and _semantic.get("override") == "ESCALATE":
            verdict = Verdict.ESCALATE
            reason = (
                f"{reason} | Semantic Judge: score={_semantic.get('score')} "
                f"flags={_semantic.get('flags')}"
            )

    # 3. persist decision (strong-typed model, serialized at DB edge)
    _tname, _tleth = _audit_tool_fields(req)
    decision = DecisionRecord(
        id=str(uuid.uuid4()),
        verdict=verdict,
        reason=reason,
        matched_rule=matched_rule,
        path=req.path,
        method=req.method,
        agent_id=req.agent_id,
        tool_name=_tname,
        tool_lethality=_tleth,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )
    # v0.2.2 (external critique #3.1): sqlite3 writes are synchronous — run in
    # the thread pool so the event loop is not blocked (Storage has an internal
    # threading.Lock to serialize access to the shared connection).
    await asyncio.to_thread(storage.save, decision.model_dump(mode="json"))

    # 4. if ALLOW and proxy mode → forward to upstream Agent
    response_body = None
    if verdict == Verdict.ALLOW and AGENT_BACKEND_URL:
        response_body = await _proxy_forward(req)

    # 5. build response — TASK-REAL-011: 回传 trace 上下文供下游链接
    #    (span_id == decision.id; 下游用 X-Parent-Span-ID 指向它)
    resp = InterceptResponse(
        verdict=verdict,
        reason=reason,
        decision_id=decision.id,
        matched_rule=matched_rule,
        trace_id=trace_id,
    )
    _trace_headers = {"X-Trace-ID": trace_id, "X-Span-ID": decision.id}

    if verdict == Verdict.DENY:
        return web.json_response(resp.model_dump(mode="json"), status=403, headers=_trace_headers)
    elif verdict == Verdict.ESCALATE:
        return web.json_response(resp.model_dump(mode="json"), status=202, headers=_trace_headers)
    else:
        result = resp.model_dump(mode="json")
        if response_body:
            result["upstream_response"] = response_body
        return web.json_response(result, status=200, headers=_trace_headers)


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
        "version": "0.4.0",
        "uptime_seconds": round(_uptime(), 2),
        "decisions_total": storage.count(),
    })


async def decisions_handler(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", 50))
    decisions = storage.get_recent(limit)
    return web.json_response({"total": len(decisions), "decisions": decisions})


async def trace_handler(request: web.Request) -> web.Response:
    """TASK-REAL-011 (C): GET /v1/trace/{trace_id} — 返回整条因果调用树。

    递归 CTE (storage.get_trace) 按 depth+timestamp 排序; 节点含杀伤半径
    审计字段 (tool_lethality) 作为边权重, 审计人员可快速定位"哪一步引入
    最大风险"。trace 不存在 → 404 (诚实语义: 资源不存在)。
    """
    trace_id = request.match_info["trace_id"]
    # TASK-REAL-011.1 (Critic-Security): URL 超长 trace_id 无 DB 风险 (参数化
    # 查询 + 无匹配即空), 但拒绝无意义的大查询 — 与 _trace_context 的
    # MAX_TRACE_ID_LEN 上限保持一致。
    if len(trace_id) > MAX_TRACE_ID_LEN:
        return web.json_response({"error": "trace_id too long"}, status=404)
    nodes = await asyncio.to_thread(storage.get_trace, trace_id)
    if not nodes:
        return web.json_response({"error": f"trace {trace_id} not found"}, status=404)
    return web.json_response({"trace_id": trace_id, "node_count": len(nodes), "nodes": nodes})


# ── OpenAI-compatible endpoint (B1: LangChain zero-touch integration) ─

# Tools whose invocation must be blocked at the LLM request level.
# LangChain exposes them as JSON functions inside the request body;
# the gateway inspects tool_calls/tools before forwarding.
# NOTE (AUDIT-0008, Reviewer REJECT fix): names are compared casefolded +
# NFKC-normalized on BOTH sides, so 'Delete_File', 'delete_fιle' (U+03B9)
# and fullwidth variants cannot bypass the exact-match blacklist.
DANGEROUS_TOOL_NAMES = ("delete_file", "delete_user", "sudo_exec", "rm_file")

# TASK-REAL-010: 归一化管线移入 src/norm.py (单一事实源) — lethality 表与
# 本模块共享同一 NFKC -> confusable map -> casefold 流程。
from .norm import norm_tool_name as _norm_tool_name


def _extract_tool_names(req: InterceptRequest) -> list:
    """Extract tool/function names from an OpenAI-format chat request.

    Type-confusion hardened (Reviewer fix): 'tools' / 'messages' /
    'tool_calls' are REQUIRED to be lists; dict bodies yield zero names
    and are treated as undecodable → the handler's fail-closed path
    takes over. Function values must be dicts, names must be strings.
    """
    body = req.body
    if isinstance(body, str) and body.strip():
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return []
    if not isinstance(body, dict):
        return []
    names = []
    tools = body.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            fn = tool.get("function")
            if isinstance(fn, dict):            # must be dict, not str
                name = fn.get("name")
                if isinstance(name, str) and name:
                    names.append(name)
    messages = body.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            tc = msg.get("tool_calls")
            if isinstance(tc, list):
                for call in tc:
                    if not isinstance(call, dict):
                        continue
                    fn = call.get("function")
                    if isinstance(fn, dict):    # must be dict, not str
                        name = fn.get("name")
                        if isinstance(name, str) and name:
                            names.append(name)
    return names


def _audit_tool_fields(req, tool_names=None) -> tuple:
    """TASK-REAL-010 (Step 1): (tool_name, tool_lethality) 审计字段。

    取请求中"杀伤半径最高"的工具名与 Ls (src/lethality.py) — 审计字段反映
    最大风险工具而非第一个遇到的名字, 供事后归因。先走精确的 OpenAI 格式
    提取; 无结果时退化为 json_path 通配提取 ($..name), 覆盖非 OpenAI
    结构化体 (如 /v1/intercept 的任意 agent 请求)。无工具声明 → (None, None)。
    """
    if tool_names is None:
        tool_names = _extract_tool_names(req)
    if not tool_names:
        body = req.body
        if isinstance(body, str) and body.strip():
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = None
        if isinstance(body, dict):
            tool_names = [v for v in _json_extract(body, "$..name") if v.strip()]
    if not tool_names:
        return None, None
    worst = max(tool_names, key=lambda n: lethality_for_tool(n))
    return worst, lethality_for_tool(worst)


def _malformed_tool_declaration(req) -> str | None:
    """Detect tool declarations that are present but structurally invalid.

    Fail-closed principle: a declaration we CANNOT verify must never be
    silently ignored and forwarded — a lenient upstream parser may still
    execute it, bypassing governance. Returns an error description or None.

    Reviewer finding R1/R3/R4 extension: 'tools' as dict, 'function' as
    string, non-str 'name' all previously produced an EMPTY name list ->
    treated as ordinary chat -> forwarded upstream. That is a bypass, not
    a crash fix. Malformed declarations must reject the request outright.
    """
    body = req.body
    if isinstance(body, str) and body.strip():
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return None  # JSON errors are handled by the caller
    if not isinstance(body, dict):
        return None  # no declaration to inspect

    tools = body.get("tools")
    if tools is not None and not isinstance(tools, list):
        return "field 'tools' must be a list"
    if isinstance(tools, list):
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                return f"tools[{i}] must be an object"
            fn = tool.get("function")
            if fn is not None and not isinstance(fn, dict):
                return f"tools[{i}].function must be an object"
            if isinstance(fn, dict):
                name = fn.get("name")
                if name is not None and not isinstance(name, str):
                    return f"tools[{i}].function.name must be a string"

    messages = body.get("messages")
    if messages is not None and not isinstance(messages, list):
        return "field 'messages' must be a list"
    if isinstance(messages, list):
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue  # non-object messages are skipped, not tool decls
            tc = msg.get("tool_calls")
            if tc is not None and not isinstance(tc, list):
                return f"messages[{i}].tool_calls must be a list"
            if isinstance(tc, list):
                for j, call in enumerate(tc):
                    if not isinstance(call, dict):
                        return f"messages[{i}].tool_calls[{j}] must be an object"
                    fn = call.get("function")
                    if fn is not None and not isinstance(fn, dict):
                        return f"messages[{i}].tool_calls[{j}].function must be an object"
                    if isinstance(fn, dict):
                        name = fn.get("name")
                        if name is not None and not isinstance(name, str):
                            return f"messages[{i}].tool_calls[{j}].function.name must be a string"
    return None


async def _deny_decision(req, reason, status, matched_rule, tool_name=None, tool_lethality=None,
                         trace_id=None, parent_span_id=None) -> web.Response:
    """Record a DENY decision and return the gateway rejection response.

    Shared by the malformed-declaration path and the dangerous-tool path
    so persistence + error shape stay identical. tool_name / tool_lethality
    (TASK-REAL-010 Step 1) audit the highest-lethality tool in the request.
    trace_id / parent_span_id (TASK-REAL-011.1, Critic-Security): 所有决策
    分支必须携带 trace 上下文 — 否则该 DENY 决策脱离调用链 (无法被
    GET /v1/trace/{trace_id} 追到), 破坏 C 阶段"全部决策在链上"承诺。
    """
    decision = DecisionRecord(
        id=str(uuid.uuid4()),
        verdict=Verdict.DENY,
        reason=reason,
        matched_rule=matched_rule,
        path=req.path,
        method=req.method,
        agent_id=req.agent_id,
        tool_name=tool_name,
        tool_lethality=tool_lethality,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )
    # v0.2.2 (external critique #3.1): sqlite3 writes are synchronous — run in
    # the thread pool so the event loop is not blocked (Storage has an internal
    # threading.Lock to serialize access to the shared connection).
    await asyncio.to_thread(storage.save, decision.model_dump(mode="json"))
    _trace_headers = {"X-Trace-ID": trace_id, "X-Span-ID": decision.id}
    return web.json_response(
        {
            "error": {
                "message": reason,
                "type": "governance_denied",
                "decision_id": decision.id,
            }
        },
        status=status,
        headers=_trace_headers,
    )


async def chat_completions_handler(request: web.Request) -> web.Response:
    """OpenAI-compatible /v1/chat/completions.

    Sidecar mode for LangChain/AutoGen: the Agent sets base_url to the
    gateway and talks normal OpenAI protocol — zero code changes. The
    gateway inspects the request (tools + tool_calls) against governance
    policy BEFORE forwarding upstream.
    """
    # TASK-REAL-011.1 (Critic-Security/DEBT-0022): 入口处提取 Trace 上下文 —
    # chat 路径全部决策分支 (malformed DENY / dangerous DENY / 主路径) 必须
    # 携带 trace_id/parent_span_id, 否则多 Agent 链跨端点断链。
    trace_id, parent_span_id = _trace_context(request.headers)
    try:
        raw = await request.read()
        body = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "invalid JSON body", "type": "invalid_request_error"}},
            status=400,
        )

    req = InterceptRequest(
        path="/v1/chat/completions",
        method="POST",
        headers={k: v for k, v in request.headers.items()},
        body=body,
        agent_id=request.headers.get("x-agent-id"),
    )

    tool_names = _extract_tool_names(req)

    # Fail-closed: a malformed tool declaration we cannot verify must
    # reject the request outright (never silently forward upstream).
    malformed = _malformed_tool_declaration(req)
    if malformed:
        _tname, _tleth = _audit_tool_fields(req, tool_names)
        return await _deny_decision(
            req,
            reason=f"工具声明畸形，无法验证 — fail-closed 拒绝: {malformed}",
            status=400,
            matched_rule="malformed-tool-declaration",
            tool_name=_tname,
            tool_lethality=_tleth,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )

    # Reviewer REJECT fix: compare NORMALIZED names (NFKC + casefold) on
    # both sides. Raw exact-match here would let 'Delete_File' /
    # 'delete_fιle' (U+03B9) slip past the blacklist even though
    # _norm_tool_name exists. Keep the original name for the reason text.
    _dangerous_norms = {_norm_tool_name(n) for n in DANGEROUS_TOOL_NAMES}
    dangerous_tools = [
        t for t in tool_names if _norm_tool_name(t) in _dangerous_norms
    ]

    if dangerous_tools:
        _tname, _tleth = _audit_tool_fields(req, tool_names)
        return await _deny_decision(
            req,
            reason=f"LLM 请求声明危险工具调用 {dangerous_tools} — 拒绝转发",
            status=403,
            matched_rule="block-dangerous-tools",
            tool_name=_tname,
            tool_lethality=_tleth,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )
    else:
        # ordinary chat → consult policy engine (allow-chat rule)
        await asyncio.to_thread(policy_engine.maybe_reload)
        rule = await asyncio.to_thread(
            policy_engine.evaluate, req.path, req.method, body
        )
        if rule is None:
            # same default semantics as /v1/intercept: no match → ALLOW
            verdict = Verdict.ALLOW
            reason = "无匹配策略，默认放行"
            status = 200
            matched_rule = None
        elif rule.action == "ALLOW":
            verdict = Verdict.ALLOW
            reason = f"匹配规则 '{rule.name}' → 放行"
            status = 200
            matched_rule = rule.name
        else:
            verdict = Verdict.ESCALATE
            reason = f"匹配规则 '{rule.name}' → 升级"
            status = 202
            matched_rule = rule.name

    _tname, _tleth = _audit_tool_fields(req, tool_names)
    decision = DecisionRecord(
        id=str(uuid.uuid4()),
        verdict=verdict,
        reason=reason,
        matched_rule=matched_rule,
        path=req.path,
        method=req.method,
        agent_id=req.agent_id,
        tool_name=_tname,
        tool_lethality=_tleth,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )
    # v0.2.2 (external critique #3.1): sqlite3 writes are synchronous — run in
    # the thread pool so the event loop is not blocked (Storage has an internal
    # threading.Lock to serialize access to the shared connection).
    await asyncio.to_thread(storage.save, decision.model_dump(mode="json"))
    _trace_headers = {"X-Trace-ID": trace_id, "X-Span-ID": decision.id}

    if verdict is not Verdict.ALLOW:
        return web.json_response(
            {
                "error": {
                    "message": reason,
                    "type": "governance_denied",
                    "decision_id": decision.id,
                }
            },
            status=status,
            headers=_trace_headers,
        )

    # forward to upstream LLM (AGENT_BACKEND_URL + /v1/chat/completions)
    upstream = f"{AGENT_BACKEND_URL}/v1/chat/completions"
    stream = bool(body and body.get("stream"))
    sse = None
    try:
        async with ClientSession(timeout=ClientTimeout(total=10, connect=3)) as session:
            async with session.post(
                upstream,
                headers={
                    k: v for k, v in request.headers.items()
                    if k.lower() in FORWARD_HEADER_WHITELIST
                },
                json=body,
            ) as resp:
                if not stream:
                    # non-streaming: buffer the full JSON response (legacy path)
                    text = await resp.text()
                    try:
                        return web.json_response(json.loads(text), status=resp.status,
                                                 headers=_trace_headers)
                    except json.JSONDecodeError:
                        return web.Response(text=text, status=resp.status,
                                            headers=_trace_headers)
                # DEBT-0004: SSE streaming pass-through — forward upstream
                # text/event-stream chunk-by-chunk without buffering (TTFT
                # no longer waits for the full response; client gets chunks
                # as they arrive). Content-Type is forced so OpenAI SDK
                # clients parse the stream correctly.
                sse = web.StreamResponse(
                    status=resp.status,
                    headers={"Content-Type": "text/event-stream"},
                )
                await sse.prepare(request)
                # TASK-REAL-011.1 (Critic-Security): 流式转发分支同样回传
                # trace 头 — 客户端 (LangChain 回调) 可读取 X-Span-ID 关联
                # 本次决策的决策记录。
                sse.headers["X-Trace-ID"] = trace_id
                sse.headers["X-Span-ID"] = decision.id
                async for chunk in resp.content.iter_chunked(1024):
                    await sse.write(chunk)
                await sse.write_eof()
                return sse
    except Exception as e:
        logger.warning("chat forward failed: %s", e)
        if sse is None:
            return web.json_response(
                {"error": {"message": "upstream LLM unreachable", "type": "upstream_error"}},
                status=502,
            )
        # stream already started — propagate so aiohttp terminates the
        # connection; the client sees a truncated SSE stream (standard).
        raise


# ── app factory ─────────────────────────────────────────────────────

async def _flush_pending_on_shutdown(app: web.Application) -> None:
    """Flush degraded-mode pending records on clean shutdown (DEBT-0010).

    storage.save() buffers entries in memory while sqlite3 is unavailable
    (DEBT-0008 degraded mode). On shutdown we retry the flush once so the
    last decisions are not lost silently. Registered via on_cleanup so it
    runs on SIGINT/SIGTERM graceful shutdown, not only SIGKILL.

    NOTE (DEBT-0002 hardening, REAL-003): must be async — aiohttp signals
    await each receiver; a sync function returning None crashes cleanup
    with "object NoneType can't be used in 'await' expression".
    """
    if storage is None:
        return
    try:
        # DEBT-0015: independent timeout — the shutdown path must NEVER exceed
        # web.run_app(shutdown_timeout=10): a stuck DB would otherwise eat the
        # whole graceful-shutdown budget and block on_cleanup completion.
        n = await asyncio.wait_for(
            asyncio.to_thread(storage.flush_pending), timeout=SHUTDOWN_FLUSH_TIMEOUT
        )
        if n:
            logger.info("shutdown: flushed %d pending decision(s)", n)
    except asyncio.TimeoutError:
        logger.warning(
            "shutdown flush_pending exceeded %ds — records remain in fallback log (DEBT-0014/0015)",
            SHUTDOWN_FLUSH_TIMEOUT,
        )
    except Exception as e:  # noqa: BLE001 — shutdown path must never crash the app
        logger.warning("shutdown flush_pending failed: %s", e)


def create_app() -> web.Application:
    global policy_engine, storage, escalate_count_since_resolve, last_escalate_time, breaker_tripped_until, _escalate_lock
    policy_engine = PolicyEngine()
    storage = Storage()
    # DEBT-0011: restore persisted breaker state (restart must not reset counters)
    breaker_state = storage.load_breaker_state()
    escalate_count_since_resolve = int(breaker_state.get("count", 0))
    last_escalate_time = float(breaker_state.get("last_escalate", 0.0))
    breaker_tripped_until = float(breaker_state.get("tripped_until", 0.0))
    _escalate_lock = asyncio.Lock()

    app = web.Application()
    app.on_cleanup.append(_flush_pending_on_shutdown)
    app.router.add_post("/v1/intercept", intercept_handler)
    app.router.add_post("/v1/chat/completions", chat_completions_handler)
    app.router.add_get("/v1/health", health_handler)
    app.router.add_get("/v1/decisions", decisions_handler)
    # TASK-REAL-011 (C): trace 因果调用树查询端点
    app.router.add_get("/v1/trace/{trace_id}", trace_handler)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    logger.info("governance-gateway v0.4.0 starting on :9000")
    # DEBT-0007: explicit shutdown_timeout (default 60s) — fast graceful
    # shutdown lets on_cleanup flush pending decisions (DEBT-0010) quickly.
    web.run_app(app, port=9000, shutdown_timeout=10)
