"""Properly migrate DEBT-0005/0006 from active to repaid section."""
import subprocess

COMMIT = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=".").stdout.strip()

lines = open("debt_registry.md", encoding="utf-8").read().split("\n")
active = []
repaid = []
section = None
for line in lines:
    if line.startswith("## 活跃债务"):
        section = "active"
        active.append(line)
        continue
    if line.startswith("## 已清偿"):
        section = "repaid"
        repaid.append(line)
        continue
    if line.strip().startswith("| DEBT-0005") or line.strip().startswith("| DEBT-0006"):
        if section == "active":
            continue  # drop from active
        else:
            repaid.append(line)
        continue
    if section == "active":
        active.append(line)
    elif section == "repaid":
        repaid.append(line)
    else:
        active.append(line)  # header preamble

# Build repaid rows
repaid_rows = [
    "| DEBT-0005 | YAML 策略无热更新（修改 policies.yaml 需重启网关生效） | `" + COMMIT + "` (TASK-REAL-001) | 2026-08-03 |",
    "| DEBT-0006 | check_policy.py AST 规则误报含 allow/deny 子串的 dict key（如 `allow_retry`） | `" + COMMIT + "` (TASK-REAL-001) | 2026-08-03 |",
]

# Insert repaid rows right after the repaid table header (before the placeholder row)
out = []
in_repaid_table = False
for line in active:
    out.append(line)
out.append("")  # separator between sections
for i, line in enumerate(repaid):
    if line.startswith("## 已清偿"):
        out.append(line)
        continue
    if line.strip().startswith("| ID |"):
        out.append(line)
        in_repaid_table = True
        continue
    if line.strip().startswith("|----"):
        out.append(line)
        out.extend(repaid_rows)
        in_repaid_table = False
        continue
    if line.strip().startswith("| （无）"):
        continue  # drop placeholder
    out.append(line)

text = "\n".join(out).rstrip() + "\n"
open("debt_registry.md", "w", encoding="utf-8").write(text)
print("migrated DEBT-0005/0006 to repaid with commit", COMMIT)
