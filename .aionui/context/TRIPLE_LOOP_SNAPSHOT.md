# 🧬 三循环治理状态快照

> 版本: v1.6.0
> 快照时间: 2026-08-03（TASK-REAL-008 清偿 DEBT-0016 — **16/16 债务清零**后更新）
> 生成方式: 自持式三循环治理引擎自动生成
> 用途: 任何新会话或新 Agent 实例可通过此文件在 30 秒内恢复完整项目状态

---

## 📌 当前状态摘要

| 指标 | 值 |
|------|-----|
| **测试全量** | 201 passed |
| **债务清偿率** | **16/16 已清偿（DEBT-0001..0017）—— 零活跃债务** |
| **活跃债务** | **无**（下一轮治理循环扫描从零基线重新开始） |
| **最近事件** | TASK-REAL-008 ✅（DEBT-0016 文档诚实性：CRITIQUE_V2 修复横幅 + EXPERIMENT_REPORT 第 7 章 + README 铁律 2/fail-closed 修正，纯文档零代码变更） |
| **CI 状态** | ✅ GATE 1-7 全绿（GATE 1: 417 asserts 0 违规；覆盖率 88.71% ≥ 60%） |
| **约束体系** | R1-R6 已固化（REAL-003..008 六连验证） |
| **提交链** | …REAL-007: `f61e5fa` → closeout: `a68288d` → REAL-008 文档: `e3f575d` → closeout: `HEAD` |

---

## 🔒 约束体系（R1-R6）

| 约束 | 定义 | 触发场景 | 固化位置 |
|------|------|----------|----------|
| **R1** | 补丁语义（不探索，锚点侦察 count==1） | 真实任务 prompt 过大 → Builder READ 截断 | `teams_collaboration.md` §2.7 |
| **R2** | JSON-RPC 直写（含 `\n` 字面量时绕 CLI 转义） | `mcp_client` `\n` 转义损坏真实代码 | `teams_collaboration.md` §2.7 |
| **R3** | 协调者兜底落盘（按 stdout 补全 + 标注） | Reviewer verdict 写盘前截断 | `teams_collaboration.md` §2.5 |
| **R4** | 规模拆分（>6 锚点/1 大文件 → 多次 Spawn 或 Coordinator 兜底） | Builder/Tester 双双 token 截断（0 writes） | `teams_collaboration.md` §2.7 |
| **R5** | 子代理 prompt 首行声明"TOOL CALLS ARE ENABLED AND REQUIRED" | S1 BLOCKED（误解"不要调用工具"为全局禁令） | `teams_collaboration.md` §2.7 |
| **R6** | 迁移私有符号前枚举全仓消费者（含 scripts/ 非测试代码），迁移后跑消费者验证 | policy_sync.py AST 消费者漏检 → GATE 7 险假漂移 | `teams_collaboration.md` §2.7 |

---

## 🔄 三循环定义

### 执行循环

| 阶段 | 动作 | 产物 |
|------|------|------|
| AUDIT | 确认任务契约完整 | 契约核对清单 |
| PLAN | 按 R4 拆分规模，确定 Spawn 次数 | Spawn 计划 |
| SPAWN | Builder + Tester 并行 → Reviewer 独立审查 | 代码变更、测试文件、审查报告 |
| VERIFY | 全量回归 + 契约验收 + file_info 自证 | 测试输出、文件大小自证 |
| MERGE | 产物合并 + 债务迁移 + relay_state 更新 | commit、债务账本更新 |

### 学习循环

| 阶段 | 动作 | 产物 |
|------|------|------|
| EXTRACT | 从执行结果中识别新约束（截断模式、规模边界、工具限制） | 约束草案 |
| GENERALIZE | 将具体教训抽象为通用规则 | 规则文本 |
| CODIFY | 写入协议 §2.7 + 注册表 + 债务账本 | 文件变更 |
| VALIDATE | 确认新规则与已有规则无冲突 + 回归测试 | 测试全绿 |

### 治理循环

| 阶段 | 动作 | 产物 |
|------|------|------|
| SCAN | 扫描债务账本 + 审计日志 + 外部批判 | 债务清单 |
| PRIORITIZE | 按风险 × 成本排序，选定最高优先级债务 | 优先级裁决 |
| CHARTER | 起草任务契约：目标/验收/角色分配 | 任务契约 |
| INITIATE | 启动执行循环 | relay_state CREATED |

---

## 📂 关键文件索引

| 文件 | 用途 | 更新规则 |
|------|------|----------|
| `debt_registry.md`（仓库根） | 债务账本 | 每次任务完成后迁移清偿债务 |
| `.aionui/scheduler/relay_state.json` | 接力状态机 | 每轮 Spawn 后更新 |
| `.aionui/audit_log.md` | 审计日志 | 每个任务完成后追加 |
| `.aionui/protocols/teams_collaboration.md` | 协作协议 | 新约束固化的唯一位置 |
| `.aionui/tools/agent_registry.yaml` | 注册表 | 新规则/新角色更新 |
| `src/` | 核心代码 | 执行循环修改 |
| `tests/` | 测试代码 | 执行循环新增 |
| `.aionui/context/TRIPLE_LOOP_SNAPSHOT.md` | 本快照 | 每次治理循环完成后更新版本号与摘要 |

> ⚠️ 路径更正：`debt_registry.md` 位于仓库根目录（非 `.aionui/` 下）。
> 此索引由 R6 精神校验（迁移/索引前枚举真实路径），避免新 Agent 读错位置。

---

## 🚀 恢复指令

如果你是新会话或新 Agent 实例，执行以下步骤恢复完整状态：

1. **加载此文件**：读取当前快照，理解状态
2. **加载协议**：读取 `.aionui/protocols/teams_collaboration.md` 获取完整协作流程
3. **加载债务账本**：读取 `debt_registry.md`（仓库根）获取剩余债务
4. **验证测试**：运行 `pytest tests/ -q` 确认 201 passed
5. **继续治理**：运行 `@governance start` 启动下一轮治理循环

---

## 📋 下一候选任务（由治理循环决定）

| 债务 | 内容 | 优先级 | 修复方向 |
|------|------|--------|----------|
| DEBT-0016 | CRITIQUE_V2/EXPERIMENT_REPORT 过时 | 🟡 MEDIUM | 文档更新/标注已修复 |

当前治理循环扫描结论：**16/16 债务清零，零活跃债务，无部署阻塞项**。DEBT-0016（文档诚实性）已清偿于 TASK-REAL-008（`e3f575d`）。

下一阶段候选（外部评审"绞杀藤模式"四层增强，零重建，共 <500 行 + 1 旁路进程）：
1. **语义旁路 Hook**（LLM-Judge 本地模型 UDS 调用，150ms 超时降级，score≥0.85 升级 ESCALATE）——补"AI 语义"空白，最贴合"治理智能体"定位
2. **json_path 工具治理**（YAML 可选字段 + jsonpath-ng 预处理，~60 行）——补 Tool Calling 粒度
3. **Trace 追踪**（trace_id/parent_span_id 列 + 递归 CTE 查询端点，~100 行）——补多智能体拓扑
4. **统计反馈调节器**（5min 扫描 DENY 高频模式 → pending_rules 推荐，~150 行）——补自演进闭环

或宣告 **"零债务 + 文档诚实" v2 稳定态**，冻结治理循环进入维护模式。

### 版本历史

- **v1.0.0**（2026-08-03）：初始快照，REAL-003 后状态（173 tests, 6/10 debts）
- **v1.1.0**（2026-08-03）：REAL-004 后更新（178 tests, 7/10 debts；R5/R6 首次应用验证有效；AUDIT-0018）
- **v1.2.0**（2026-08-03）：REAL-005 后更新（181 tests, **10/10 debts 全清偿**；all-gates 单一检查；AUDIT-0019）
- **v1.3.0**（2026-08-03）：B3 验证 + 批判 SCAN（187 tests；DEBT-0011~0016 登记；AUDIT-0020；提交 48c3453+31ec19d）
- **v1.4.0**（2026-08-03）：REAL-006 + CI 门控修复（194 tests；DEBT-0011/0012 清偿；GATE 1 21→0 + GATE 6 修复；AUDIT-0021；提交 dfaef6b）
- **v1.5.0**（2026-08-03）：REAL-007 清偿 DEBT-0013/0014/0015（201 tests；FALLBACK_PATH 落盘备份 + MAX_FLUSH_ATTEMPTS 重试上限/退避 + SHUTDOWN_FLUSH_TIMEOUT=8 独立超时；覆盖率 88.71%；AUDIT-0022；提交 f61e5fa + closeout；DEBT-0017 补登 dfaef6b）
- **v1.6.0**（2026-08-03）：REAL-008 清偿 DEBT-0016 文档诚实性（纯文档零代码；CRITIQUE_V2 修复横幅 + EXPERIMENT_REPORT 第 7 章 + README 铁律 2/fail-closed 6 处；201 tests 回归；AUDIT-0023；提交 e3f575d + closeout；**16/16 债务清零**）

---

**快照结束。此文件由三循环治理引擎自动生成，每次治理循环完成后自动更新。**
