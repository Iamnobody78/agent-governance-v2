"""Tool lethality weights (Ls) — 可解释治理主控 Step 1 (TASK-REAL-010).

Lethality Score 是工具"杀伤半径"的静态度量（0.0 = 无害, 1.0 = 系统级毁灭），
作为可解释审计字段 (DecisionRecord.tool_name / tool_lethality) 的数据基础：
每次决策记录请求中杀伤半径最高的工具名与分值，供事后归因与仪表盘聚合。

设计原则:
  - 基线在此处 (Python 常量) 为兜底实现; 可解释主控 Step 2+ 计划把权重表
    迁移到 YAML（"策略是数据"铁律）。此表只做审计记账, 不参与决策路径。
  - 名称匹配复用 src/norm.py 的归一化管线（单一事实源, DEBT-0002 精神）。
  - 未知工具取 0.6（中等）——"无法评估即按中等风险记账"的审计语义,
    不放大也不隐匿。
"""

from typing import Optional

from .norm import norm_tool_name

# 工具杀伤半径权重表 (Ls): 归一化后的工具名 -> 0.0-1.0 静态度量。
# 语义分档:
#   0.1-0.3  只读/无害 (search, query, read, list, get)
#   0.4-0.6  轻量状态变更 / 未知工具默认 (send, notify, copy, move)
#   0.5-0.7  状态写入 (create, edit, write, update, append)
#   0.8-0.95 系统执行 / 删除 / 提权 (execute_command, rm_*, sudo_*)
TOOL_LETHALITY: dict = {
    # ── read-only (0.1-0.3) ──
    "search": 0.2, "query": 0.2, "read": 0.2, "read_file": 0.2,
    "list": 0.2, "get": 0.2, "lookup": 0.2, "retrieve": 0.2,
    "stat": 0.2, "ls": 0.1, "cat": 0.2, "fetch_url": 0.3, "get_weather": 0.1,
    # ── light state change (0.4-0.6) ──
    "notify": 0.4, "send_message": 0.5, "email": 0.5, "copy": 0.6,
    "move": 0.6, "rename": 0.6, "mkdir": 0.5, "upload": 0.7, "http_post": 0.6,
    # ── write / state-change (0.5-0.7) ──
    "write": 0.7, "write_file": 0.7, "edit": 0.7, "edit_file": 0.7,
    "create": 0.7, "create_file": 0.7, "append": 0.7, "append_file": 0.7,
    "update": 0.7, "update_file": 0.7, "overwrite": 0.7, "overwrite_file": 0.7,
    "patch": 0.7, "apply_patch": 0.7, "config_write": 0.7, "set_env": 0.75,
    "set_secret": 0.8, "set_permissions": 0.85, "chmod": 0.85,
    # ── system execution (0.85-0.95) ──
    "execute_command": 0.95, "execute": 0.9, "system_run": 0.95,
    "shell_exec": 0.95, "run_shell": 0.95, "terminal_exec": 0.95,
    "bash": 0.95, "sh": 0.95, "subprocess": 0.95, "run": 0.85,
    "python_exec": 0.9, "exec": 0.9, "eval": 0.9,
    # ── deletion / destructive (0.9-0.95) ──
    "delete": 0.95, "delete_file": 0.95, "delete_user": 0.95,
    "delete_all": 0.95, "rm": 0.95, "rm_file": 0.95, "rmdir": 0.9,
    "drop": 0.95, "drop_table": 0.95, "truncate": 0.95, "format": 0.95,
    # ── privilege (0.85-0.95) ──
    "sudo_exec": 0.95, "sudo": 0.95,
}

_DEFAULT_LETHALITY = 0.6  # 未知工具: 中等杀伤记账（审计语义, 非决策）


def lethality_for_tool(name: Optional[str]) -> float:
    """返回归一化后工具名的杀伤半径 (Ls); 未知/空值取默认 0.6。

    审计字段始终有界 (0.0-1.0) —— 归一化前名称经 norm_tool_name 折叠
    同形异义字, 'delete_fιle' (U+03B9) 与 'delete_file' 同分。
    """
    if not isinstance(name, str) or not name.strip():
        return _DEFAULT_LETHALITY
    return TOOL_LETHALITY.get(norm_tool_name(name), _DEFAULT_LETHALITY)
