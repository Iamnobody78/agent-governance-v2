"""B1: Real LangChain Agent — zero-touch integration via gateway base_url.

This agent imports ONLY LangChain SDK — zero knowledge of the gateway.
It talks normal OpenAI protocol; the gateway intercepts /v1/chat/completions
transparently (sidecar mode). Governance is invisible to this code.

Run (against the stub LLM):
    python examples/langchain_agent.py --gateway http://127.0.0.1:9000

The agent's LLM calls are routed through the gateway, which inspects
tool declarations and blocks dangerous tool calls (DENY) before they
reach the upstream LLM.
"""

import argparse
import os
import sys

# ── zero gateway imports: only LangChain SDK ─────────────────────────
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


@tool
def get_time() -> str:
    """Return the current wall-clock time as a string."""
    import datetime

    return datetime.datetime.now().isoformat()


@tool
def delete_file(path: str) -> str:
    """Delete the file at the given path. DANGEROUS — should be governed."""
    import os

    os.remove(path)
    return f"deleted {path}"


_ALL_TOOLS = {"get_time": get_time, "delete_file": delete_file}


def build_agent(gateway_url: str, tools=None):
    """Create a LangChain agent whose LLM calls go through the gateway.

    tools: list of tool names ('get_time' | 'delete_file') — default both.
    A safe agent (tools=['get_time']) exercises the ALLOW path; including
    'delete_file' exercises the DENY path — governance blocks the request
    when the LLM request declares a dangerous tool.
    """
    tool_objs = [_ALL_TOOLS[name] for name in (tools or ["get_time", "delete_file"])]
    llm = ChatOpenAI(
        base_url=f"{gateway_url}/v1",   # ← the ONLY gateway reference: base_url
        api_key="test-key",              # gateway does not validate keys (sidecar)
        model="test-model",
        temperature=0,
    )
    return create_agent(model=llm, tools=tool_objs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", default=os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000"))
    parser.add_argument("--prompt", default="What time is it?")
    args = parser.parse_args()

    agent = build_agent(args.gateway)
    # real agent invocation — this is what a production LangChain app runs
    result = agent.invoke({"messages": [{"role": "user", "content": args.prompt}]})
    print("AGENT RESULT:", result["messages"][-1].content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
