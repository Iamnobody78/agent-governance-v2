# 🧬 三循环治理状态快照

> 版本: v1.10.0
> 快照时间: 2026-08-03（TASK-REAL-012 Phase 4——治理大脑 Phase 1：可解释引擎 rationale + 五级判定后更新）
> 生成方式: 自持式三循环治理引擎自动生成
> 用途: 任何新会话或新 Agent 实例可通过此文件在 30 秒内恢复完整项目状态

---

## 📌 当前状态摘要

| 指标 | 值 |
|------|-----|
| **测试全量** | 329 passed（319 基线 + 10 新增，零回归） |
| **覆盖率** | 90.12%+（门槛 ≥ 60%，Phase 4 变更未降） |
| **债务清偿率** | 活跃 3（DEBT-0018/0020/0021，无阻塞）；DEBT-0022 已清偿（REAL-011.1）、DEBT-0019 已清偿（REAL-011） |
| **活跃债务** | DEBT-0018（body 大小上限, MEDIUM）、DEBT-0020（输出侧语义, LOW）、DEBT-0021（timeout 分支不覆盖 json_path 规则, LOW, 已文档化接受） |
| **最近事件** | TASK-REAL-012 Phase 4 ✅（治理大脑 Phase 1：Verdict 五级 ALLOW/ALLOW_WITH_WARNING/ESCALATE/DENY/SUSPEND + DecisionRecord.rationale 第 13 列 + X-Governance-Warning 响应头 + create_app(config_path) 策略注入；10 测试；GATE 8 5/5 PASS） |
| **CI 状态** | ✅ GATE 1-8 全绿（GATE 8 = Critic Agent 五批判者，329 tests 全量回归 exit 0） |
| **约束体系** | R1-R6 已固化 + 防伪造三原则（真实执行输出/一次一 Phase/独立可复核提交） |
| **提交链** | …REAL-011: `d95f83c` → Phase 1: `0e389ea` → Phase 2: `c6a3a95` → 协议: `0f636e2` → Phase 3: `45e4561` → Phase 4: `42d938d`（+ closeout 提交） |

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
4. **验证测试**：运行 `pytest tests/ -q` 确认 329 passed
5. **继续治理**：运行 `@governance start` 启动下一轮治理循环

---

## 📋 下一候选任务（由治理循环决定）

| 债务 | 内容 | 优先级 | 修复方向 |
|------|------|--------|----------|
| DEBT-0018 | 请求/响应无大小上限 | 🟡 MEDIUM | 网关层 body 上限（独立任务或并入 D 阶段） |
| DEBT-0020 | 输出侧语义评估缺失 | 🟢 LOW | 代理转发后异步补判 agent_response（待 A 就绪） |
| DEBT-0021 | timeout 分支不覆盖 json_path 规则 | 🟢 LOW | 已文档化接受；后续可在 danger.py 增加 body 感知或接受纵深防御 |
| DEBT-0022 | chat/completions 路径未注入 trace 上下文 | 🟢 LOW | ✅ 已清偿（REAL-011.1 `6c25bd9`：chat 提取 trace + 两处 DENY 注入 + 主路径 DecisionRecord + 全响应分支回传头 + MAX_TRACE_ID_LEN=128） |

当前治理循环扫描结论：**18 项债务已清偿（含 DEBT-0019/0022），3 项活跃（DEBT-0018/0020/0021，均无阻塞）**。TASK-REAL-012 自进化引擎 Phase 4 完成（治理大脑 Phase 1：rationale + 五级判定），L1-L4 层架构全部落地。

下一阶段候选（按 B→C→D→E(自进化) 顺次）：
1. **TASK-REAL-012 Phase 5：Context Hook HMAC**（约 100 行，HMAC 签名 context 头防伪造）——L3 治理大脑收尾，**待用户批准**
2. **D：统计反馈调节器**（5min 扫描 DENY 高频模式 → pending_rules 推荐）——已在 Phase 2（Meta-Harness 适配器 `c6a3a95`）吸收：generate_policy_suggestions + pending_rules/ 候选 YAML
2. **外部评审后续候选**（协商/学习引擎、Tree-sitter AST、HMAC Context Hook、Shadow Saga、Rust）：治理大脑已裁决并入 5 层架构（L3/L2）；L3 可解释引擎 + 五级判定 Phase 4 已落地（rationale + ALLOW_WITH_WARNING/SUSPEND）；**HMAC Context Hook 为 Phase 5**（约 100 行，待批准）；Tree-sitter/Rust 等阶段未来化
3. **A 生产化**：拉取 qwen2.5:7b-instruct-q4_K_M（JUDGE_MODEL 热切换零代码）或 Bastion 70M 级联，实测延迟/准确率——待硬件到位
4. **可解释主控 Step 2+**：CoT 推理链 / 上下文漂移（标记"待 A 就绪"）；Ls 权重表届时迁移 YAML
5. **输出侧语义**（DEBT-0020）：代理转发后异步补判 agent_response

### 版本历史

- **v1.0.0**（2026-08-03）：初始快照，REAL-003 后状态（173 tests, 6/10 debts）
- **v1.1.0**（2026-08-03）：REAL-004 后更新（178 tests, 7/10 debts；R5/R6 首次应用验证有效；AUDIT-0018）
- **v1.2.0**（2026-08-03）：REAL-005 后更新（181 tests, **10/10 debts 全清偿**；all-gates 单一检查；AUDIT-0019）
- **v1.3.0**（2026-08-03）：B3 验证 + 批判 SCAN（187 tests；DEBT-0011~0016 登记；AUDIT-0020；提交 48c3453+31ec19d）
- **v1.4.0**（2026-08-03）：REAL-006 + CI 门控修复（194 tests；DEBT-0011/0012 清偿；GATE 1 21→0 + GATE 6 修复；AUDIT-0021；提交 dfaef6b）
- **v1.5.0**（2026-08-03）：REAL-007 清偿 DEBT-0013/0014/0015（201 tests；FALLBACK_PATH 落盘备份 + MAX_FLUSH_ATTEMPTS 重试上限/退避 + SHUTDOWN_FLUSH_TIMEOUT=8 独立超时；覆盖率 88.71%；AUDIT-0022；提交 f61e5fa + closeout；DEBT-0017 补登 dfaef6b）
- **v1.6.0**（2026-08-03）：REAL-008 清偿 DEBT-0016 文档诚实性（纯文档零代码；CRITIQUE_V2 修复横幅 + EXPERIMENT_REPORT 第 7 章 + README 铁律 2/fail-closed 6 处；201 tests 回归；AUDIT-0023；提交 e3f575d + closeout；**16/16 债务清零**）
- **v1.7.0**（2026-08-03）：REAL-009 A 阶段语义旁路 LLM-Judge（judge/llm_judge.py + src/semantic_hook.py + main.py 集成 + 14 测试；215 tests；架构全链路验证 PASS；0.5b 模型边界诚实记录；DEBT-0018/0019/0020 登记；AUDIT-0024）
- **v1.8.0**（2026-08-03）：REAL-010 B 阶段 json_path 工具治理 + 可解释主控 Step 1（src/policy.py 零依赖 JSONPath 子集 + 条件规则 + norm.py/lethality.py 新建 + DecisionRecord/storage 10 列审计 Schema + _migrate 无损迁移 + policies.yaml v0.2.0 两条 json_path 规则 + GATE 5/7 联动；250 tests；覆盖率 90.07%；DEBT-0021 登记；AUDIT-0025；提交 e45a02b）
- **v1.9.0**（2026-08-03）：REAL-011 C 阶段 Trace 因果追踪（DecisionRecord/InterceptResponse + trace_id/parent_span_id + storage 12 列迁移 + idx_trace（_migrate 后）+ get_trace 递归 CTE（max_depth=50/max_nodes=500）+ intercept 入口 X-Trace-ID/X-Parent-Span-ID 集成 + X-Span-ID 响应头 + GET /v1/trace/{trace_id} + v0.4.0；20 测试；270 tests；覆盖率 90.12%；DEBT-0019 清偿（d95f83c）、DEBT-0022 登记；AUDIT-0026）

---

**快照结束。此文件由三循环治理引擎自动生成，每次治理循环完成后自动更新。**
