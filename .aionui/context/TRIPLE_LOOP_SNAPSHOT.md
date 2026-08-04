# 🧬 三循环治理状态快照

> 版本: v1.33.0-memory
> 快照时间: 2026-08-04（记忆持久化协议闭环 — write_memory.py 写入即索引 + knowledge_distill.py 启发式蒸馏（frontmatter 剥离/引号标签/正文日期兜底/全类型关键词加权/中英 hint 别名/tag 专属 fallback）→ 74 条真实记忆蒸馏出 12 条经验模式 + load_lessons.py 注入 [LESSON_CONTEXT]；25 测试全绿；代理提议裁决: 拒绝 agent-memory(Go 二进制供应链) + PLUR(Hermes-only)，自研零依赖 Python 三件套）
> 最近审计: AUDIT-0054（Ollama 自激活）+ AUDIT-0053（数据流补强）+ AUDIT-0052（记忆协议测试 25 项）
> 生成方式: 自持式三循环治理引擎自动生成
> 用途: 任何新会话或新 Agent 实例可通过此文件在 30 秒内恢复完整项目状态

---

## 📌 当前状态摘要

| 指标 | 值 |
|------|-----|
| **测试全量** | ~880+ passed（分批全绿；记忆协议三件套 +25：write_memory 9 + knowledge_distill 9 + load_lessons 7；test_p2_env 17、test_p2_research_runner 13、test_taint 11、test_research_mcp 5；环境级慢非回归） |
| **覆盖率** | 87%（`--source=src` 实测；门槛 ≥ 60%） |
| **债务清偿率** | 活跃 3（DEBT-0018/0020/0021，无阻塞） |
| **活跃债务** | DEBT-0018（body 大小上限, MEDIUM）、DEBT-0020（输出侧语义, LOW）、DEBT-0021（timeout 分支不覆盖 json_path 规则, LOW, 已文档化接受）；已知边界: ① 拼接形态已由 src/taint.py 闭合（函数参数跨界/条件分支/属性链传播仍为边界）；② DROP DATABASE = grammar ERROR 节点（L2 YAML 兜底） |
| **最近事件** | **记忆持久化协议** ✅（三阶段学习保留闭环 P0 捕获→P1 蒸馏→P2 注入：write_memory.py 零依赖写入+自动索引+去重；knowledge_distill.py 74 条真实记忆蒸馏 12 模式（MCP 契约×31/绝对路径×27/timeout×19/回归×16/零误报×14/UTF-8×10/认证×10）；load_lessons.py [LESSON_CONTEXT] 注入；裁决: 拒 agent-memory+PLUR 外部依赖）。此前: **P2 自激活** ✅（本地 Ollama 零-key：真实报告含 APA 引用，来源 truefoundry；gh013 清扫后首个真实推送 bfce10a 经 ls-remote 验证）。**数据流分析** ✅（src/taint.py 拼接盲区闭合）。**路径 B MCP** ✅ |
| **CI 状态** | ✅ GATE 1-8 全绿（quality/policy/critic 3 job + all-gates 聚合；GATE 3 junitxml + 真实退出码 + ci_diagnose） |
| **约束体系** | R1-R6 已固化 + 防伪造三原则（真实执行输出/一次一 Phase/独立可复核提交） |
| **提交链** | …`bc815a4` 批判审计修复 → `a8b5bc4` taint + P2 MCP → `bfce10a` Ollama 自激活 → 快照 v1.33.0-memory（记忆协议三件套待提交） |

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
4. **验证测试**：运行 `pytest tests/ -q` 确认 574 passed
5. **继续治理**：运行 `@governance start` 启动下一轮治理循环

---

## 📋 下一候选任务（由治理循环决定）

| 债务 | 内容 | 优先级 | 修复方向 |
|------|------|--------|----------|
| DEBT-0018 | 请求/响应无大小上限 | 🟡 MEDIUM | 网关层 body 上限（独立任务或并入 D 阶段） |
| DEBT-0020 | 输出侧语义评估缺失 | 🟢 LOW | 代理转发后异步补判 agent_response（待 A 就绪） |
| DEBT-0021 | timeout 分支不覆盖 json_path 规则 | 🟢 LOW | 已文档化接受；后续可在 danger.py 增加 body 感知或接受纵深防御 |
| DEBT-0022 | chat/completions 路径未注入 trace 上下文 | 🟢 LOW | ✅ 已清偿（REAL-011.1 `6c25bd9`：chat 提取 trace + 两处 DENY 注入 + 主路径 DecisionRecord + 全响应分支回传头 + MAX_TRACE_ID_LEN=128） |
| DEBT-0027 | 身份认证缺失：L2-L5 治理能力暴露于未认证访问（外部评审缺口 #1） | 🟢 LOW | ✅ 已清偿（P6 `9e91c03`：TenantAuth API key 认证 + X-Tenant-ID 一致性 403 + tenant 作用域隔离 + HMAC 服务签名复用；420 tests；AUTH_ENABLED 开关兼容模式） |

当前治理循环扫描结论：**23 项债务已清偿（含暗雷区 DEBT-0023~0026 与 P6 DEBT-0027），3 项活跃（DEBT-0018/0020/0021，均无阻塞）**。暗雷区 4/4 收官 + P6 身份认证/多租户闭合（外部评审缺口 #1）。

下一阶段候选（按 B→C→D→E(自进化) 顺次）：
1. **P7 代理自举**（`src/agent_tools/`：`self_critic/self_trace/self_heal` 复用 L4/L5 现有能力暴露为代理可调用工具；集成 self_evolution_protocol）——**方向已批准，防御顺序排在 P6 之后（身份边界先于自我治理 API）**
2. **D：统计反馈调节器**（5min 扫描 DENY 高频模式 → pending_rules 推荐）——已在 Phase 2（Meta-Harness 适配器 `c6a3a95`）吸收：generate_policy_suggestions + pending_rules/ 候选 YAML
2. **外部评审后续候选**（协商/学习引擎、Tree-sitter AST、Shadow Saga、Rust）：治理大脑已裁决并入 5 层架构（L3/L2）——可解释引擎 + 五级判定（Phase 4）与 HMAC Context Hook（Phase 5）均已落地；**Tree-sitter/Rust 等阶段未来化**（无硬依赖，可随时立项）
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
- **v1.10.0**（2026-08-03）：TASK-REAL-012 Phase 1-4（Critic GATE 8 五批判者 + Meta-Harness 适配器/沙箱 + 治理大脑 rationale + 五级判定 ALLOW/ALLOW_WITH_WARNING/ESCALATE/DENY/SUSPEND；331 tests；AUDIT-0027/0028；提交 45e4561+42d938d+7c29be7+ae311aa）
- **v1.11.0**（2026-08-03）：TASK-REAL-012 Phase 5 Context Hook HMAC（src/context_hmac.py + 信任门 + _signed_trace_headers + 16 测试；347 tests；AUDIT-0029；提交 be8289b；五层架构 L1-L5 全部闭环）
- **v1.12.0**（2026-08-03）：暗雷区修复 P0-P2（P0 异常堆栈日志 1ef39a0 + P1 语义钩子异步弱监督/撤销注册表 be0b5ee + P2 SQLite WAL/批量提交 c40dc41；370 tests；覆盖率 87%（--source=src 含 meta_harness）；DEBT-0023/0024/0025 清偿、DEBT-0026 登记待 P3；AUDIT-0030/0031/0032；GATE 8 5/5 PASS）
- **v1.13.0**（2026-08-03）：暗雷区 P3 json_path 前缀索引树（JsonPathIndex 首段键桶化剪枝 + segments 缓存，391 tests，DEBT-0026 清偿，AUDIT-0033；暗雷区 4/4 收官，P6 身份认证+多租户待用户裁决）
- **v1.14.0**（2026-08-03）：P6 服务身份认证 + 多租户隔离（TenantAuth 401/403 + tenant 作用域 + HMAC 签名复用 + AUTH_ENABLED 兼容模式，420 tests，DEBT-0027 清偿，AUDIT-0034；外部评审缺口 #1 闭合；架构文档同步加 auth 层；P7 代理自举方向已批准）
- **v1.15.0**（2026-08-03）：P7 代理自举工具集（src/agent_tools/ 三工具 self_critic/self_trace/self_heal 复用 L4/L5 + 11 测试防纸面 + self_evolution_protocol.md；431 tests；AUDIT-0035；提交 c6b9484）
- **v1.16.0**（2026-08-03）：Phase HA 高可用（src/ha/：FileLock OS 级互斥 + Lease TTL5s + FailoverCoordinator 单写者模型；docs/ha_design.md；441 tests；AUDIT-0036；提交 864c890）
- **v1.17.0**（2026-08-03）：P8 认证层（src/certification/：ED25519 sign/verify + 密钥自动生成落盘 PKCS8 chmod600 + CLI；450 tests；AUDIT-0037；提交 8e2b71b；证明协议地基）
- **v1.18.0**（2026-08-03）：P9 外部代理示例（examples/：external_agent_demo 进程内 agent_tools + langchain/autogen 零侵入 base_url 被动 sidecar + _stub_llm 测试双 + run_examples.ps1/sh 双 runner；真实 SDK 调用被网关 403 治理；修复既有 TestZeroTouchClaim 3 失败；450 tests；GATE 8 5/5 PASS；AUDIT-0038）
- **v1.19.0**（2026-08-03）：P10 开源就绪（CONTRIBUTING.md 含 Agent 治理流程 + .github/workflows/ci.yml GATE 1-8 真实 CI + docs/CERTIFICATION.md 认证指南 + README 徽章块；git push origin main 同步 24 commits；GATE 5 实测 sign→verify OK；CI GATE 7 自验证快照版本 + AUDIT 链；AUDIT-0039）
- **v1.20.0**（2026-08-03）：P11 元编程声明（裁决：补全"自生成"为 ✅——src/codegen/generator.py 编译式生成 + _generated_matches.py 入库 + tests/test_codegen.py 38 测试含 16 项运行时等价性 + policy_sync.py --generate 漂移自愈；docs/META_CAPABILITIES.md 7 项诚实声明（✅×5 ⚠️×2 人类在环）；README 元能力徽章；488 tests；AUDIT-0040）
- **v1.24.0**（2026-08-03）：社区标准合规补全（CODE_OF_CONDUCT.md + SECURITY.md + Issue/PR 模板 + dependabot.yml + codeql.yml + README 3 社区徽章；13 项开源社区标准核查全闭合；542 tests；AUDIT-0045）
- **v1.25.0**（2026-08-03）：Tree-sitter AST 硬阻断引擎（src/ast_guard.py + payload_extractor.py + queries/{python,bash,sql}.scm + policy.py Priority 0 前门 + main.py fail-closed 注入；三约束验收：P1 Capture 校验/P2 Payload 提取/P3 Bash 零硬编码；依赖锁定 tree-sitter==0.21.3+tree-sitter-languages==1.5.0；574 tests；GATE 8 5/5 PASS；AUDIT-0046）

---

**快照结束。此文件由三循环治理引擎自动生成，每次治理循环完成后自动更新。**
