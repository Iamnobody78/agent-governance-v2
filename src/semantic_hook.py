"""Semantic bypass hook — TASK-REAL-009 (A-phase, LLM-Judge integration).

Invoked AFTER the static YAML verdict is determined, BEFORE the decision is
persisted, so an upgraded verdict is fully audited. NEVER downgrades:
- DENY stays DENY (static rules are the final word for blocking).
- ALLOW/ESCALATE may be upgraded to ESCALATE when the external LLM-Judge
  returns score >= threshold.

Fail-soft by design: any timeout / connection error / malformed response
returns None and the static verdict stands untouched (the gateway must never
depend on the judge being up).

Configuration (env vars, read once at call time so tests can override):
- SEMANTIC_HOOK_ENABLED  : "1" to enable (default "0" — opt-in)
- SEMANTIC_JUDGE_URL     : judge endpoint (default http://127.0.0.1:8765/v1/judge)
- SEMANTIC_HOOK_TIMEOUT  : seconds (default 0.15 — must stay tiny; see README)
- SEMANTIC_HOOK_THRESHOLD: score at which ALLOW -> ESCALATE (default 0.85)
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

SEMANTIC_HOOK_ENABLED = os.environ.get("SEMANTIC_HOOK_ENABLED", "0") == "1"
SEMANTIC_JUDGE_URL = os.environ.get("SEMANTIC_JUDGE_URL", "http://127.0.0.1:8765/v1/judge")
SEMANTIC_HOOK_TIMEOUT = float(os.environ.get("SEMANTIC_HOOK_TIMEOUT", "0.15"))
SEMANTIC_HOOK_THRESHOLD = float(os.environ.get("SEMANTIC_HOOK_THRESHOLD", "0.85"))

# TASK-REAL-009 / DEBT-0018: bounded input — the judge only ever sees a
# truncated prefix (meta-prompt rule: first ~512 tokens + tail). Full text
# never leaves the gateway process.
PROMPT_MAX_CHARS = 2000
RESPONSE_MAX_CHARS = 1000


def is_enabled() -> bool:
    return SEMANTIC_HOOK_ENABLED


def truncate_prompt(prompt: str, max_chars: int = PROMPT_MAX_CHARS) -> str:
    """DEBT-0018 (A-phase scope): bounded judge input, head + tail preserved."""
    if prompt is None:
        return ""
    prompt = str(prompt)
    if len(prompt) <= max_chars:
        return prompt
    head = max_chars // 2
    tail = max_chars // 2
    return prompt[:head] + "\n...[truncated]...\n" + prompt[-tail:]


def extract_prompt(body) -> str:
    """Best-effort extraction of the user prompt from an InterceptRequest body."""
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        if isinstance(body.get("prompt"), str):
            return body["prompt"]
        messages = body.get("messages")
        if isinstance(messages, list):
            parts = []
            for m in messages:
                if isinstance(m, dict) and isinstance(m.get("content"), str):
                    parts.append(m["content"])
            if parts:
                return "\n".join(parts)
        try:
            return json.dumps(body, ensure_ascii=False)
        except (TypeError, ValueError):
            return ""
    return str(body)


async def semantic_hook(user_prompt: str, timeout: float = SEMANTIC_HOOK_TIMEOUT) -> Optional[Dict]:
    """Ask the LLM-Judge for a risk score. Returns {override, score, flags} or None.

    None means 'no semantic signal' — the static verdict stands. Never raises.
    """
    if not is_enabled():
        return None
    if not user_prompt or not user_prompt.strip():
        return None
    truncated = truncate_prompt(user_prompt)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SEMANTIC_JUDGE_URL,
                json={"user_prompt": truncated},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("semantic judge status %s", resp.status)
                    return None
                data = await resp.json()
    except (asyncio.TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as e:
        logger.debug("semantic hook degraded (%.40s) — static verdict stands", e)
        return None

    try:
        score = float(data["score"])
        flags = data.get("flags", [])
        if not isinstance(flags, list):
            flags = []
    except (KeyError, TypeError, ValueError):
        logger.warning("semantic judge malformed payload: %.200s", data)
        return None

    if score >= SEMANTIC_HOOK_THRESHOLD:
        return {"override": "ESCALATE", "score": score, "flags": [str(f) for f in flags]}
    return {"override": None, "score": score, "flags": [str(f) for f in flags]}


# ── P1 (暗雷区) 异步弱监督 ────────────────────────────────────────────
# 主链路不再 await judge（消除启用时 +150ms 阻塞）。后台任务（create_task）
# 调用 judge → 高风险时撤销 trace 链；judge 被注入攻破最坏 = 多撤一条链
# （SUSPEND 待人工复审），绝不放行 DENY —— 只升不降原则保持。

async def semantic_audit_async(trace_id: str, user_prompt: str,
                               base_reason: str = "") -> Optional[Dict]:
    """后台弱监督审计（fire-and-forget，供 asyncio.create_task 调度）。

    返回 judge 结果（{override, score, flags} 或 None）。副作用:
      - score >= 阈值 → revoke_registry.revoke(trace_id)（后续请求短路 SUSPEND）
      - 审计事件以 warning 日志记录（撤销的持久化发生在后续请求的
        SUSPEND DecisionRecord 落库时 —— 见 main.py intercept 入口）
    永不抛异常（fail-soft：judge 不可用 → 返回 None，静默降级）。
    """
    from .revoke import revoke_registry
    if not is_enabled():
        return None
    try:
        result = await semantic_hook(user_prompt)
    except Exception as e:  # noqa: BLE001 — background task must never crash loop
        logger.warning("semantic audit crashed (%.80s) — trace=%s", e, trace_id)
        return None
    if result and result.get("override") == "ESCALATE":
        score = result.get("score", 0.0)
        flags = result.get("flags", [])
        reason = (f"语义审计撤销 (score={score}, flags={flags})"
                  f"{' | ' + base_reason if base_reason else ''}")
        revoke_registry.revoke(trace_id, reason, score)
        logger.warning("semantic audit REVOKED trace=%s score=%s flags=%s",
                       trace_id, score, flags)
    return result
