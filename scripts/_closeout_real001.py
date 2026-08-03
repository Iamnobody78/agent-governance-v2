"""TASK-REAL-001 closeout: append AUDIT-0013, mark DEBT-0005/0006 repaid."""
import re

# 1. Append AUDIT-0013
audit = """

## AUDIT-0013 · 2026-08-03T12:45:00Z

- PR: N/A · 调度层真实项目治理验证（TASK-REAL-001）
- 主题: 用治理框架（Builder→Tester→Reviewer + MCP 共享通道）清偿真实债务批次
- 变更文件: `src/policy.py` (+PolicyEngine.reload/maybe_reload mtime 热重载 + 原子 swap), `src/main.py` (2 处 maybe_reload 集成), `scripts/check_policy.py` (visit_Dict 精确 token 匹配), `tests/test_policy_hot_reload.py` (+5), `tests/test_check_policy_ast.py` (+5), `.aionui/scheduler/relay_state.json`, `.aionui/tools/agent_registry.yaml`, `.aionui/protocols/teams_collaboration.md`
- 变更量: +1148/-46 (approx)
- 结果: **TASK-REAL-001 PASS-WITH-NOTES** —— 两个真实债务清偿，152 passed（142+10）
- 问题: 2（均为非 artifact 缺陷）
- Reviewer: REAL001_Reviewer（Spawn，MCP 只读），PASS-WITH-NOTES，verdict 落盘 reviewer_verdict.md
- Commit: 本次提交
- 结论:
  - 主: **真实项目治理验证成立** —— 债务来自外部批判（2.3 热更新 / 6.1 AST 误报），非自造；契约验收全满足：改 YAML 无需重启即生效（HOT-RELOAD OK）、check_policy 对 allow_retry 不再误报、152 全绿
  - 主: 调度层真实场景边界暴露（3 条新约束）: (a) 真实任务 prompt 过大 → Builder READ 阶段截断（v1 0 writes）→ 写后审协议触发 v2 恢复，证明恢复机制有效; (b) mcp_client \\n 转义在真实代码（f-string 含 \\n）下损坏 → 直接 JSON-RPC 重提交; (c) Reviewer 在 verdict 写盘前截断 → Coordinator 按其输出补全落盘（写后审协议兜底）
  - 主: 测试优先裁决再次兑现 —— Tester 契约要求 str() 强制 + None 默认 → Builder 2 行最小修复
  - 次: probe e 确认 maybe_reload 恰 2 处（L94/L471），接口向后兼容（PolicyEngine(config_path=p) 用法无破坏）
  - 防口頭验证: 152 全量回归 + Reviewer 独立重跑 10/10 + 5 项契约探测 + probe e 补跑
"""

with open(".aionui/audit_log.md", "a", encoding="utf-8") as f:
    f.write(audit)
print("audit appended", len(audit), "chars")

# 2. Mark DEBT-0005/0006 repaid in debt_registry.md
reg = open("debt_registry.md", encoding="utf-8").read()
replaced = []
for debt_id, tag in [("DEBT-0005", "DEBT-0005(已清偿: TASK-REAL-001)"), ("DEBT-0006", "DEBT-0006(已清偿: TASK-REAL-001)")]:
    # find the table row containing the debt id and mark it
    lines = reg.split("\n")
    out = []
    for line in lines:
        if debt_id in line and line.strip().startswith("|"):
            # append status tag in the last cell
            if "已清偿" not in line:
                line = line.rstrip() + " " + tag + " |" if not line.rstrip().endswith("|") else line.rstrip()[:-1] + " " + tag + " |"
            replaced.append(debt_id)
        out.append(line)
    reg = "\n".join(out)

open("debt_registry.md", "w", encoding="utf-8").write(reg)
print("registry marked:", replaced)
