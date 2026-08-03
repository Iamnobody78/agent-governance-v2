"""B1 e2e: real LangChain SDK against the live gateway.

Runs the actual examples/langchain_agent.py (which imports only LangChain
SDK) against a live gateway + stub LLM. Proves end-to-end:
  Agent (ChatOpenAI base_url=gateway) → gateway /v1/chat/completions
  → policy check → forward stub LLM → reply back to Agent.

Run with venv that has langchain:
  .venv-b1/Scripts/python.exe scripts/_b1_e2e.py
"""

import asyncio
import json
import sys
import threading
from pathlib import Path

import aiohttp

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import src.main as main_module  # noqa: E402

STUB_PAYLOAD = {
    "choices": [{"message": {"role": "assistant", "content": "stub: 2026-08-03T12:00:00"}}]
}


def run_agent(gateway_url: str, prompt: str, result_holder: list, tools=None):
    """Run the real LangChain agent in a thread (it's sync)."""
    sys.path.insert(0, str(REPO / "examples"))
    from langchain_agent import build_agent

    agent = build_agent(gateway_url, tools=tools)
    out = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    result_holder.append(out["messages"][-1].content)


async def main():
    # 1. stub LLM upstream
    async def upstream(request):
        body = await request.json()
        # echo how many tools were declared (evidence of passthrough)
        return aiohttp.web.json_response(STUB_PAYLOAD)

    upstream_app = aiohttp.web.Application()
    upstream_app.router.add_post("/v1/chat/completions", upstream)
    u_runner = aiohttp.web.AppRunner(upstream_app)
    await u_runner.setup()
    u_site = aiohttp.web.TCPSite(u_runner, "127.0.0.1", 0)
    await u_site.start()
    u_port = u_site._server.sockets[0].getsockname()[1]

    # 2. real gateway in front
    old_url = main_module.AGENT_BACKEND_URL
    main_module.AGENT_BACKEND_URL = f"http://127.0.0.1:{u_port}"
    g_app = main_module.create_app()
    g_runner = aiohttp.web.AppRunner(g_app)
    await g_runner.setup()
    g_site = aiohttp.web.TCPSite(g_runner, "127.0.0.1", 0)
    await g_site.start()
    g_port = g_site._server.sockets[0].getsockname()[1]
    gateway_url = f"http://127.0.0.1:{g_port}"

    try:
        # 3a. SAFE agent (tools=[get_time]) → ALLOW path
        result = []
        await asyncio.to_thread(
            run_agent, gateway_url, "What time is it?", result, tools=["get_time"]
        )
        assert result, "safe agent produced no output"
        print("SAFE AGENT REPLY:", result[0])
        assert "stub" in result[0], "safe agent did not receive upstream reply"

        # 3b. DANGEROUS agent (default tools incl. delete_file) → DENY path
        #     gateway 403s the request that declares delete_file, so the
        #     upstream stub is never reached and agent errors out.
        try:
            await asyncio.to_thread(
                run_agent, gateway_url, "delete everything", result
            )
            denied = False
        except Exception as e:
            denied = "403" in str(e) or "governance_denied" in str(e)
        assert denied, "dangerous agent should be blocked with 403"

        # 4. decisions persisted for both paths
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{gateway_url}/v1/decisions?limit=10") as r:
                data = await r.json()
        allows = [d for d in data["decisions"] if d["verdict"] == "ALLOW"]
        denies = [d for d in data["decisions"] if d["verdict"] == "DENY"]
        assert allows, "no ALLOW decision persisted for the safe agent chat"
        assert denies, "no DENY decision persisted for the dangerous agent"
        print(f"PERSISTED: {data['total']} decisions "
              f"({len(allows)} ALLOW, {len(denies)} DENY)")
        print("B1 E2E PASS: safe→ALLOW, dangerous→DENY, both persisted")
    finally:
        main_module.AGENT_BACKEND_URL = old_url
        await g_runner.cleanup()
        await u_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
