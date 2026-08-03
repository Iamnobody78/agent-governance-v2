# 🔍 Audit Log — 永久审查记录

> 每次代码审查必须在此记录。本文件永久保留，不可删除。
> 协议依据：PR Review Loop v1.0 §6、Teams 协作协议 v2.0。

## AUDIT-0008 — 2026-08-03T07:00:00Z

- PR: N/A（B1: LangChain 集成实验 + 团队化两阶段 Spawn 验证）
- 标题: OpenAI 兼容端点 + 真实 LangChain 零侵入集成（B 阶段 B1）
- 变更文件: `src/main.py` (+chat_completions_handler, +DANGEROUS_TOOL_NAMES, +_extract_tool_names, +_norm_tool_name, +_malformed_tool_declaration, +_deny_decision), `examples/langchain_agent.py`, `tests/test_integration_langchain.py` (+22), `scripts/b1_e2e.py`, `EXPERIMENT_B_REPORT.md`
- 变更行数: +380/-20
- 评级: 自验证 A- → **Spawn Reviewer REJECT**（R1-R4 四洞）→ 修复后 A
- 结论: **PASS → REJECT → PASS**（团队化两阶段 Spawn 完整循环）
- 问题数: 自验证 0 → Reviewer 发现 HIGH:2 MEDIUM:1 LOW:1 → 修复后 0
- Reviewer: **Spawn `reviewer-b1`**（独立视角，非自我审查）
- Commit: 待提交
- 备注:
  - **零侵入证据**: `examples/langchain_agent.py` AST 扫描 0 个 gateway import；只设 base_url；不调用 /v1/intercept（测试断言）
  - **声明级拦截**: LangChain create_agent 首轮请求声明全部工具 → 网关检测 delete_file → 403，upstream 0 调用
  - **真实 SDK E2E**: `scripts/b1_e2e.py`（venv: langchain 1.3.14）安全 Agent ALLOW + 危险 Agent DENY，双向入库
  - 自发现修复 1: rule=None 时 chat handler 崩溃 → 与 /v1/intercept 一致的默认放行语义
  - 自发现修复 2: e2e 中 thread.join() 死锁网关事件循环 → asyncio.to_thread
  - 自发现修复 3: tools 字符串参数 → 工具对象映射（_ALL_TOOLS）
  - **🔴 Reviewer R1 (HIGH) 类型混淆**: `tools` 传 dict → 迭代 keys → 0 名字 → ALLOW 透传。修复: `_extract_tool_names` 强制 `isinstance(x, list)`，dict 形状 fail-closed；新增 `_malformed_tool_declaration` 结构校验，畸形声明整体 400 拒绝（不静默忽略）
  - **🔴 Reviewer R2 (HIGH) Unicode/大小写变体**: `Delete_File`、`delete_fιle`(U+03B9) 绕过精确匹配。修复: `_norm_tool_name` 三阶段管道 NFKC → confusable 同形映射（希腊 iota/西里尔/罗马数字）→ casefold；**关键发现: NFKC+casefold 本身不折叠同形字符，必须显式 confusable 表**
  - **🟡 Reviewer R3 (MEDIUM) 字符串 function**: `"function": "delete_file"`（str 非 dict）→ `str.get` AttributeError → 500。修复: `isinstance(fn, dict)` 防护 + 畸形声明 400 拒绝（原测试曾误判为"忽略+透传"即可，全栈测试暴露深层 bypass）
  - **🟢 Reviewer R4 (LOW) 非字符串 name**: list/dict/数字 name 被静默追加。修复: `isinstance(name, str) and name` 守卫
  - 验证: 75/75 测试（+11 Reviewer 回归：R1 dict 形状 fail-closed ×3、R2 unicode/case/fullwidth 全栈 DENY ×3 + 持久化 ×1、R3 字符串 function 400 ×1、R4 非字符串 name ×1）+ GATE 1-7 全绿 + health_score 100/100
  - 已知限制: stub LLM（非真实 GPT）、AutoGen B2 未测、b1_e2e 依赖 venv 未接 CI

---

## AUDIT-0007 — 2026-08-03T06:00:00Z

- PR: N/A（用户元批判 + 团队制落地决策）
- 标题: 团队制基础设施 + GATE 6/7 + 元概念批判落地
- 变更文件: `scripts/meta_security_scanner.py`, `scripts/policy_sync.py`, `scripts/health_score.py`, `scripts/concept_gap_audit.py`, `src/policy.py`, `pyproject.toml`, `.aionui/index.md`, `.aionui/handoffs/`, `.aionui/decisions/`, `.aionui/failures/`, `debt_registry.md`, `.github/workflows/ci.yml`
- 变更行数: +320/-15
- 评级: 审查 A-（含自发现修复）
- 结论: **PASS**（7 门控全绿 + 53/53 测试 + 健康评分 100/100）
- 问题数: 新增 0（自发现并修复 2 个自身 bug）
- Reviewer: 自我审查（GATE 6/7 对抗验证触发）
- Commit: 0f25b41, e9f7d3c（后续修复）
- 备注:
  - **元批判裁决**: 拒绝 51 概念清单 + 拒绝"摘除器/假测试生成器"（v1 病复现）；保留概念核查器为审计工具（concept_gap_audit.py）
  - GATE 6 落地: AST 反模式扫描（熔断放行/超时放行/静默吞异常/无 normpath startswith）；对抗验证 fixture 4 反模式全抓，删除 fixture 出库
  - GATE 7 落地: 策略-代码漂移检测（DENY+ESCALATE 覆盖 + action 原始值校验）；对抗验证小写 deny/孤儿前缀 REJECT
  - GATE 6 自发现 bug: `max(f.severity)` 引用 for 循环残留 WindowsPath 变量 → 生成器表达式修复（e9f7d3c）
  - GATE 7 自发现 bug: `.upper()` 归一化掩盖小写 action → 检查原始值（FAILURE-0002 归档）
  - health_score.py: 4 门控实测评分（100/100 验证），暴露 pytest rootdir 漂移问题（FAILURE-0001 归档）
  - pyproject.toml 锁 rootdir: 修复 python -m pytest 在子仓库运行时漂移到父工作区
  - 团队制 5 机制骨架: index.md / handoffs / decisions / failures / debt_registry（4 活跃债务全 LOW，0 阻塞）

---

---

## AUDIT-0001 — 2026-08-03T00:00:00Z

- PR: N/A（实验阶段，非 PR 触发）
- 标题: 熔断器时间衰减 + ALLOW 重置修复
- 变更文件: `src/main.py`, `tests/test_circuit_breaker.py`, `scripts/check_test_quality.py`
- 变更行数: +170/-10
- 评级: A-
- 结论: PASS
- 问题数: HIGH:0 MEDIUM:1 LOW:2
- Reviewer: Teams 两阶段 Spawn (Builder + Reviewer)
- Commit: `898fc21`
- 备注: Reviewer 发现 MEDIUM（覆盖检查单向）+ 2 LOW（常量复制、KeyError 风险），全部修复后 PASS

## AUDIT-0002 — 2026-08-03T01:00:00Z

- PR: N/A（实验阶段）
- 标题: teams v2.0 协议 + policy_probe 工具
- 变更文件: `.aionui/protocols/teams_collaboration.md`, `examples/policy_probe.py`
- 变更行数: +167/-69
- 评级: B+
- 结论: PASS
- 问题数: HIGH:0 MEDIUM:0 LOW:0
- Reviewer: Coordinator 直接验证（exit 0 + 30/30 测试）
- Commit: `6d051e2`
- 备注: policy_probe 双向一致性检查（DENY/ESCALATE 覆盖 + ALLOW 不误判）

## AUDIT-0003 — 2026-08-03T02:00:00Z

- PR: N/A
- 标题: CI GATE 5 - policy consistency probe
- 变更文件: `.github/workflows/ci.yml`
- 变更行数: +16/-0
- 评级: B+
- 结论: PASS
- 问题数: HIGH:0 MEDIUM:0 LOW:0
- Reviewer: Coordinator 验证（YAML 语法 + 本地 exit 0）
- Commit: `f541481`
- 备注: 修正了依赖 bug——policy_probe import src.main 需要完整依赖，非仅 pyyaml

## AUDIT-0004 — 2026-08-03T03:00:00Z

- PR: N/A（协议验证：用 Reviewer Prompt Template v1.0 实际 Spawn）
- 标题: GATE 5 审查 → REJECT → 修复 → PASS 完整闭环
- 变更文件: `examples/policy_probe.py`, `src/main.py`, `config/policies.yaml`
- 变更行数: +33/-22
- 评级: C → A-（修复后）
- 结论: **REJECT → PASS**（首个真实 REJECT 闭环）
- 问题数: HIGH:1 MEDIUM:2 LOW:4 → 修复后 HIGH:0 MEDIUM:0
- Reviewer: Spawn 代理 `reviewer-gate5`（模板注入，6 turns）
- Commit: 待提交
- 备注: **HIGH** — action 大小写/笔误绕过（`deny` 被运行时 else→ALLOW 放行且 probe 静默跳过）→ 修复：action 白名单校验 + 孤儿前缀反向检查 + DANGEROUS_PREFIXES 提升为模块常量。验证：篡改 YAML 后 probe exit 1，恢复后 exit 0

## AUDIT-0005 — 2026-08-03T04:00:00Z

- PR: N/A（外部安全审查，4 洞全确认）
- 标题: 安全加固 v0.2.0 —— 熔断 fail-closed + 路径规范化 + 计数器加锁 + Header 白名单
- 变更文件: `src/main.py`, `tests/test_security_hardening.py`, `tests/test_circuit_breaker.py`, `tests/test_intercept.py`
- 变更行数: +118/-36
- 评级: 审查 C（4 洞）→ 修复后 A-
- 结论: **REJECT → PASS**（外部审查触发，非自我审查）
- 问题数: HIGH:2 MEDIUM:2 LOW:1 → 修复后 HIGH:0 MEDIUM:0
- Reviewer: 外部安全审查（用户提供，非 Spawn）
- Commit: 待提交
- 备注:
  - 🔴 HIGH-1 熔断 DDoS 后门: `escalate_count >= LIMIT` 时 `ALLOW` → 改为 `DENY`（失去判断力=拒绝，不是放行）。同步 3 处测试断言 ALLOW→DENY
  - 🔴 HIGH-2 路径绕过: `_is_dangerous()` 的 `startswith` 无法覆盖 `/api/v1/delete` 变体与 `/api/delete/../admin` 遍历 → 加 `posixpath.normpath` 规范化 + 边界匹配 + 危险尾段段级防御（8 个单元测试覆盖遍历/变体/编码斜杠/边界）
  - 🟡 MEDIUM-3 全局竞态: `escalate_count_since_resolve` 无锁 → `asyncio.Lock` 保护读写（并发 5 请求精确计数测试）
  - 🟡 MEDIUM-4 Header 透传: `Authorization` 直接透传上游 → `FORWARD_HEADER_WHITELIST` 白名单（真实 echo 上游验证 auth 不泄漏）
  - 🟢 LOW: 流式请求体（记为已知限制，不修）
  - 附带清理: 删除从未被调用的死代码 `resolve_policy()`（v1 玩具算式残留）
  - 验证: 44/44 测试 + GATE 1-5 全过（覆盖率 92% > 60%）
  - 教训: 熔断器"修复 fail-open 又引入 fail-open"——安全逻辑的递归缺陷。修复必须从语义出发（fail-closed），而非从参数出发

## AUDIT-0006 — 2026-08-03T05:00:00Z

- PR: N/A（外部审查：models.py 类型断层分析）
- 标题: 类型连续性修复 —— DecisionRecord 强类型化 + body Union + Docstring 去应激
- 变更文件: `src/models.py`, `src/main.py`, `tests/test_models_types.py`
- 变更行数: +63/-20
- 评级: 审查 C（4 缺陷 + 1 额外发现）→ 修复后 A-
- 结论: **REJECT → PASS**（外部审查触发）
- 问题数: 4 缺陷 + 1 额外 → 修复后 0
- Reviewer: 外部审查（用户提供）
- Commit: 待提交
- 备注:
  - 🟡 类型断层: `DecisionRecord.verdict: str` / `timestamp: str` 降级弱类型 → 改为 `Verdict` 枚举 + 时区感知 `datetime`，`field_serializer` 在持久化边界序列化（类型安全贯穿响应层→存储层）
  - 🟡 `body: Optional[str]` 强制重复编解码 → 改为 `Optional[Union[Dict, str]]`，`_proxy_forward` 自动区分；策略匹配可直接用结构化数据
  - 🟡 应激式 Docstring `— Pydantic, no plain dataclass.` → 功能性描述（类型策略声明）
  - 🟡 时区丢失: `DecisionRecord.timestamp` 存 ISO8601 时区保留（round-trip 测试验证 tzinfo 非空）
  - 🟡 额外发现: `agent_id` 在 DecisionRecord 曾缺失（storage 表有列）→ 已恢复
  - 附带清理: main.py 移除未用的 `datetime`/`timezone` import；修复 PowerShell 损坏的 UTF-8 乱码字符 `�X`
  - 验证: 53/53 测试（新增 9 个类型连续性测试）+ GATE 1-5 全过（覆盖率 92.28% > 60%）
  - GATE 2 豁免: 53 > 50 上限，`# GATE2-APPROVED:` 标记（理由：全部为真实运行时验证，非 v1 式假测试膨胀）

---

## AUDIT-0009 — 2026-08-03T09:00:00Z

- PR: N/A（B 阶段 B2: AutoGen 零侵入集成 + 外部批判证据核验 + v0.2.2 工程修复）
- 标题: AutoGen GroupChat 多 Agent 零侵入集成完成 + 外部批判 15 项声明逐条证据核验
- 变更文件: `src/main.py` (+_deny_decision async, +3x storage.save to_thread), `src/policy.py` (Rule Literal + __post_init__ fail-closed + 大小写归一), `src/storage.py` (threading.Lock 序列化共享连接), `tests/test_policy_config_validation.py` (+7), `scripts/b2_e2e.py` (断言修复: proposer 合法转发 vs 危险声明转发), `EXPERIMENT_B_REPORT.md` (+B2 章节), `debt_registry.md` (+DEBT-0005..0008), `.aionui/decisions/DECISION-0002-B2-AUTOGEN.md` (+阶段4日志)
- 变更行数: +250/-40
- 评级: 外部批判(网页版 DeepSeek) 15 项声明 → 证据核验后: 12 STALE(已修复) + 2 夸大 + 2 VALID(本轮修复) + 1 部分有效(登记债务)
- 结论: **B2 E2E PASS**（safe→ALLOW 4 转发 / dangerous→403 0 危险声明上游 / 6 决策入库）; 全量回归 **94/94**
- 问题数: VALID 2（YAML action 无校验 typo 静默放行、storage.save 同步阻塞事件循环）→ 已修复; 债务 4 条登记（DEBT-0005..0008）
- Reviewer: 外部独立批判（网页版 DeepSeek）+ 本会话逐条证据核验（防口头通过协议）
- Commit: 待提交
- 备注:
  - 🔴 VALID #2.1: `Rule.action: str` 无约束 → `Literal["ALLOW","DENY","ESCALATE"]` + `__post_init__` 校验 fail-closed（typo 配置拒绝启动而非静默 ALLOW）; 顺带修复大小写 bug: YAML `deny` 原与 `== "DENY"` 严格比较不匹配会静默变 ALLOW
  - 🟡 VALID #3.1: `storage.save` 3 处同步直调阻塞事件循环 → `await asyncio.to_thread` + Storage 内部 `threading.Lock` 序列化共享 sqlite3 连接（check_same_thread=False）; `_deny_decision` 需同步改 `async def`（2 调用点加 await）
  - 🟢 STALE 清单（批判基于 v0.1.0 快照行号）: 熔断器 fail-open(1.1)、路径 startswith 绕过(1.2)、无并发锁(1.3)、上游无超时(1.4)、通配符边界(2.2)、连接新建(3.2)、无索引(3.3)、models 类型断层(4.1)、body 类型(4.2)、测试导入 examples(5.1)、外部服务依赖(5.2)、熔断与 README 不一致(7.2) — 均已在 AUDIT-0005/0008 修复
  - 🟡 夸大: 无优雅停机(1.5, aiohttp 默认 shutdown_timeout=60s)、请求体全量内存(1.6, 拦截 JSON 决策量级小)
  - 验证: 94/94 测试（87 + 7 新增异常路径）+ `b2_e2e.py` 真实 AutoGen E2E PASS + 三文件 py_compile OK
  - 防口头通过: 本审计所有"已修复"声明均有当前源码行号证据（见会话核验表）

## AUDIT-0010 — 2026-08-03T10:30:00Z

- PR: N/A（调度层第一阶段: 自动接力循环）
- 标题: 调度层第一阶段落地 — Builder→Reviewer 自动接力 + 先落盘协议 + 外环注册表
- 变更文件: `src/time_utils.py` (+新, 实验产物), `tests/test_time_utils.py` (+新, 9 函数 15 用例), `.aionui/scheduler/relay_state.json` (+新, 接力状态机), `.aionui/tools/agent_registry.yaml` (+新, 外环注册表), `.aionui/protocols/teams_collaboration.md` (+§2.5 自动接力循环), `.aionui/scheduler/work/TASK-SCHED-001/{builder_output,reviewer_verdict}.md` (+新, 接力证据)
- 变更行数: +170/-0
- 结论: **TASK-SCHED-001 PASS**（1 轮完成）— 调度层第一阶段验证成功
- 问题数: 1（Reviewer v1 截断 → 先落盘协议修复）
- Reviewer: 独立 Reviewer 子代理（SCHED001_Reviewer_v2, PASS, 证据见 reviewer_verdict.md）
- Commit: 待提交
- 备注:
  - 🔴 实测发现（调度层关键约束）: Spawn 子代理无法互相对话/嵌套（schema 明示禁止 shared state/sequential coordination）→ "自动接力"= Coordinator 驱动多轮 Spawn，共享上下文=工作区文件系统; 禁止在单次 Spawn 内构建跨代理依赖链
  - 🔴 实测发现: Spawn 子代理可能未完成即被截断返回（Reviewer v1 仅 2 turns）→ 关键产物必须"先落盘、后完善"（verdict 写文件优先于深度审查），接力判断只认落盘文件不认 stdout
  - 🟢 验证: TASK-SCHED-001 Builder 15 passed / Reviewer 独立重跑 15 passed + AST 精确 3 函数 + EPOCH import OK → PASS; 全量回归 94+15=109? （time_utils 新增 15 用例, 全量 109 passed 见回归输出）
  - 防口头通过: Builder 报告与 Reviewer 独立观察逐项核对一致（测试数/AST/import），偏差为 0

## AUDIT-0011 — 2026-08-03T11:35:00Z

- PR: N/A（调度层第二阶段: 并行接力 + 合并审查）
- 标题: 三角色并行接力验证完成 — Builder+Tester 并行 → Reviewer 合并审查（TASK-SCHED-002）
- 变更文件: `src/task_scheduler.py` (+新, 90 行, 优先级队列), `tests/test_task_scheduler.py` (+新, 177 行 21 用例), `.aionui/scheduler/relay_state.json` (TASK-SCHED-002 三角色历史), `.aionui/protocols/teams_collaboration.md` (+§2.6 并行接力), `.aionui/tools/agent_registry.yaml` (Tester 角色验证 + 并行规则)
- 变更行数: +290/-10
- 结论: **TASK-SCHED-002 PASS**（1 轮完成，含 1 次 Tester 截断修复轮）— 调度层第二阶段验证成功
- 问题数: 1（Tester v1 截断未落盘 → TEST(2) 修复轮成功）
- Reviewer: 独立 Reviewer 子代理（SCHED002_Reviewer, PASS, 21 passed 独立重跑 + AST + 契约探测 + 双报告交叉一致 0 偏差）
- Commit: 待提交
- 备注:
  - 🔴 并行语义实测: 同一 Spawn 多任务 = 真并行（Tester 在 Builder 产物缺失时仍正常执行契约测试编写）; 但并行角色间无实现可见性 → **接口契约必须预共享**（双方 prompt 携带相同契约，否则产物必然不匹配）
  - 🔴 截断容错实测: Tester v1 5 turns 被截断 → 测试文件未落盘 → 接力中断; 修复 = TEST(2) 轮强制"先写文件再运行" + Coordinator 每轮验证产物存在/完整（行数/字节数），缺失即自动修复轮
  - 🟢 验证: Builder SELF-CHECK OK + Tester 21 passed + Reviewer 独立重跑 21 passed（0.08s）+ AST ['TaskScheduler'] 精确 + 方法无多余 + 契约探测（空 pop None / peek 非破坏 / ValueError）全过; 双报告交叉一致; 全量回归 **130 passed**（109+21）
  - 防口头通过: Reviewer 未信任 Builder/Tester 报告，全部独立重跑; 发现的唯一偏差为运行时长噪声（0.10s vs 0.08s）非矛盾


## AUDIT-0012 · 2026-08-03T12:15:00Z

- PR: N/A · 调度层接力: MCP 工具共享（TASK-SCHED-003）
- 主题: 子代理经 MCP 共享工具通道 —— Builder/Tester 写、Reviewer 读，全部 artifact 经 MCP 落盘
- 变更文件: src/rate_limiter.py (+新建 RateLimiter token bucket，1479 chars，含 remaining() key 校验), 	ests/test_rate_limiter.py (+新建 3185 bytes，12 测试), scripts/mcp_client.py (+新建 MCP 客户端 CLI: tools/call，\n 转义，exit 0/1/2), .aionui/scheduler/relay_state.json (TASK-SCHED-003 COMPLETED + MCP channel 自证), .aionui/protocols/teams_collaboration.md (更新), .aionui/tools/agent_registry.yaml (更新)
- 变更量: +550/-0
- 结果: **TASK-SCHED-003 PASS-WITH-NOTES** —— MCP 共享通道验证成功；142 passed（130+12）
- 问题: 2（均为非 artifact 缺陷）
- Reviewer: SCHED003_Reviewer（Spawn），PASS-WITH-NOTES，verdict 落盘 reviewer_verdict.md
- Commit: 本次提交
- 结论:
  - 主: MCP 共享通道全链路验证 —— Builder write_file(1479) + Tester write_file(3185) 并行 → Reviewer 仅经 MCP read_file/file_info 读取（8/8 OK）→ 独立重跑 12 passed + AST OK + 契约探测 OK；沙箱拒绝路径逃逸，全部 repo-relative
  - 主: 写后审协议再次兑现 —— 首次 tester_report.md 声称写入但 file_info Not found（子代理截断）→ 经 MCP 通道重建并带完整命令轨迹
  - 主: 并行分歧裁决 —— Tester 对契约严格解释（remaining() 也校验空键）vs Builder 宽松实现 → 协调者判测试优先（契约原文 + 纵深防御），Builder round 2 修复后 12 passed
  - 次: note1 = 协调者 probe 脚本行 bug（refill() 返回 None 非 bool），修正后 CONTRACT PROBE OK，非 artifact 缺陷
  - 次: note2 = mcp_client cp950 codec 读取带 BOM 的 teams_collaboration.md 失败（仅客户端显示问题，服务器/沙箱正常）
  - 防口頭验证: Reviewer 未信任任何报告，全部独立重跑；MCP file_info 逐文件自证大小（1425/1500/2872/3185 bytes 全部匹配）


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
  - 主: 调度层真实场景边界暴露（3 条新约束）: (a) 真实任务 prompt 过大 → Builder READ 阶段截断（v1 0 writes）→ 写后审协议触发 v2 恢复，证明恢复机制有效; (b) mcp_client \n 转义在真实代码（f-string 含 \n）下损坏 → 直接 JSON-RPC 重提交; (c) Reviewer 在 verdict 写盘前截断 → Coordinator 按其输出补全落盘（写后审协议兜底）
  - 主: 测试优先裁决再次兑现 —— Tester 契约要求 str() 强制 + None 默认 → Builder 2 行最小修复
  - 次: probe e 确认 maybe_reload 恰 2 处（L94/L471），接口向后兼容（PolicyEngine(config_path=p) 用法无破坏）
  - 防口頭验证: 152 全量回归 + Reviewer 独立重跑 10/10 + 5 项契约探测 + probe e 补跑
