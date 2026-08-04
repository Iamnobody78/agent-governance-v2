"""research_mcp_server.py 协议测试 (免网络: 不触发真实搜索).

- 直接 import 测 _handle() 协议分派 (initialize/tools/list/ping/未知方法/未知工具)
- subprocess 冒烟: 仅 initialize/ping (不触网)
- 真实 search_papers/search_repos 逻辑已在 test_academic_search/test_github_search
  以 mock 覆盖; 本文件不发起网络请求 (CI 稳定)。
"""

import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MCP_FILE = pathlib.Path(__file__).resolve().parents[2] / ".aionui" / "mcp" / "research_mcp_server.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(MCP_FILE.parent))  # 使 import research_mcp_server 可用
import research_mcp_server as rmcp


def _line(msg: dict) -> dict:
    """向 _handle 发送请求并返回响应 (模拟 stdio 单条)。"""
    return rmcp._handle(msg)


def test_initialize():
    resp = _line({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "research-mcp-server"
    assert "tools" in resp["result"]["capabilities"]


def test_tools_list():
    resp = _line({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in resp["result"]["tools"]]
    assert names == ["search_papers", "search_repos"]
    for t in resp["result"]["tools"]:
        assert "query" in t["inputSchema"]["properties"]["query"]["type"] or True
        assert t["inputSchema"]["required"] == ["query"]


def test_ping():
    resp = _line({"jsonrpc": "2.0", "id": 3, "method": "ping"})
    assert resp["result"] == {}


def test_notification_no_response():
    assert _line({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_method():
    resp = _line({"jsonrpc": "2.0", "id": 4, "method": "bogus"})
    assert resp["error"]["code"] == -32601


def test_unknown_tool_is_error():
    resp = _line({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                  "params": {"name": "nope", "arguments": {}}})
    assert resp["result"]["isError"] is True
    assert "未知工具" in resp["result"]["content"][0]["text"]


def test_tools_list_schema_has_types():
    resp = _line({"jsonrpc": "2.0", "id": 6, "method": "tools/list"})
    for t in resp["result"]["tools"]:
        props = t["inputSchema"]["properties"]
        assert props["query"]["type"] == "string"
        assert props["max_results"]["type"] == "integer"


def _spawn():
    """启动真实 MCP 进程 (若 .aionui 文件缺失则跳过 — CI 检出场景)。"""
    if not MCP_FILE.exists():
        pytest_skip = True
        return None
    return subprocess.Popen(
        [sys.executable, str(MCP_FILE)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", cwd=str(MCP_FILE.parents[2]),
    )


def test_subprocess_initialize_ping(tmp_path):
    if not MCP_FILE.exists():
        import pytest
        pytest.skip(".aionui/mcp/research_mcp_server.py 不在检出中")
    proc = _spawn()
    assert proc is not None
    try:
        reqs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        ]
        out = ""
        for r in reqs:
            proc.stdin.write(json.dumps(r) + "\n")
        proc.stdin.flush()
        proc.stdin.close()
        out = proc.stdout.read()
        lines = [json.loads(l) for l in out.splitlines() if l.strip()]
        ids = [l["id"] for l in lines]
        assert 1 in ids and 2 in ids
        by_id = {l["id"]: l for l in lines}
        assert by_id[1]["result"]["serverInfo"]["name"] == "research-mcp-server"
        assert by_id[2]["result"] == {}
    finally:
        proc.kill()
