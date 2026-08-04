"""scripts/p2_research_runner.py — gpt-researcher 独立 runner (子进程入口)。

被 research_mcp_server.py 的 run_research 工具以 subprocess 调用:
  .venv-research\\Scripts\\python.exe scripts/p2_research_runner.py \
      --query "..." [--report-type research_report] [--max-sources 10]

输出: 单行 JSON (stdout):
  {"ok": true,  "report": "<markdown 报告>", "sources": N}
  {"ok": false, "error": "<可读错误>"}
失败时同样 exit 0 (JSON 携带 ok 字段); 进程级异常 (超时被杀) 由调用方处理。

环境: 读取 <repo-root>/.env (DEEPSEEK_API_KEY 等, 手工解析零依赖);
      gpt-researcher 的模型配置经环境变量注入 (见 deploy_p2_research.ps1
      生成的 .env 模板)。gpt_researcher 未安装时返回可读错误而非 traceback。

诚实边界: gpt-researcher 0.16+ 要求 Python>=3.12 (隔离 .venv-research);
      本 runner 只编排, 不内嵌搜索/生成逻辑。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _REPO_ROOT / ".env"


def load_env(path: Path = _ENV_PATH) -> None:
    """手工解析 .env (key=value, # 注释, 引号剥离), 注入 os.environ。

    绝不覆盖已存在的环境变量 (已显式设置的优先)。缺失文件静默。
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def _gpt_researcher_cls():
    """延迟导入 GPTResearcher; 缺失时抛 ImportError(可读消息)。"""
    try:
        from gpt_researcher import GPTResearcher
    except ImportError as e:
        raise ImportError(
            f"gpt_researcher 未安装 (Python>=3.12 的 .venv-research 隔离环境)。"
            f"请先运行: powershell -ExecutionPolicy Bypass -File "
            f"scripts/deploy_p2_research.ps1 -DryRun 查看计划, 去掉 -DryRun 执行。"
            f"底层错误: {e}"
        ) from e
    return GPTResearcher


async def _run_research(query: str, report_type: str) -> tuple[str, int]:
    GPTResearcher = _gpt_researcher_cls()
    researcher = GPTResearcher(query=query, report_type=report_type)
    await researcher.conduct_research()
    report = await researcher.write_report()
    # 来源数量尽力统计 (gpt-researcher 无稳定公共计数接口, 缺失时返回 0)
    sources = 0
    try:
        ctx = getattr(researcher, "context", None)
        if isinstance(ctx, list):
            sources = len(ctx)
    except Exception:  # noqa: BLE001 — 统计失败不阻断
        sources = 0
    return report, sources


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="gpt-researcher 独立 runner")
    ap.add_argument("--query", required=True, help="研究问题或主题")
    ap.add_argument("--report-type", default="research_report",
                    choices=["research_report", "summary", "deep_analysis"],
                    help="报告类型 (默认 research_report)")
    ap.add_argument("--max-sources", type=int, default=10,
                    help="最大来源数 (由 gpt-researcher 自行消费, 默认 10)")
    args = ap.parse_args(argv)

    load_env()

    # stdout 必须干净: 研究输出只走结果 JSON (log 消息不影响协议)
    try:
        report, sources = asyncio.run(_run_research(args.query, args.report_type))
    except ImportError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001 — 研究失败返回可读错误
        print(json.dumps(
            {"ok": False, "error": f"研究执行失败: {type(e).__name__}: {e}"},
            ensure_ascii=False))
        return 0

    print(json.dumps(
        {"ok": True, "report": report, "sources": sources,
         "query": args.query, "report_type": args.report_type},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
