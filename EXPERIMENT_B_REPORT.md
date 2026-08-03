# EXPERIMENT_B_REPORT.md — B 阶段：LangChain/AutoGen 真实集成

> 实验目标：验证 Sidecar 网关对真实 Agent 框架（LangChain）的"零侵入"宣称。
> 对照基线：A 阶段的 `/v1/intercept` 显式调用模式（Agent 必须知道网关存在）。
> B1 结论日期: 2026-08-03 · AUDIT-0008

## B1 结果摘要

| 验证维度 | 结果 | 证据 |
|----------|:---:|------|
| Agent 零代码修改 | ✅ | `examples/langchain_agent.py` AST 扫描: 0 个 gateway import，只 import LangChain SDK |
| 被动拦截（非显式调用） | ✅ | Agent 只设 `base_url=网关/v1`，不调用 `/v1/intercept`（测试断言） |
| 真实 SDK 端到端 ALLOW | ✅ | 安全 Agent → 网关 → stub LLM → 回复返回（`b1_e2e.py`） |
| 危险工具声明级 DENY | ✅ | 含 `delete_file` 的 Agent 请求被 403 拦截，upstream 0 次调用 |
| 决策入库 | ✅ | 双向各 1 条：ALLOW + DENY，`/v1/decisions` 可查 |
| 全量回归 | ✅ | 64/64 测试 + GATE 1-7 全绿 |

## B1 关键技术发现

### 发现 1：LangChain 的 `base_url` 是唯一集成点（真正的零侵入）

```python
llm = ChatOpenAI(base_url=f"{gateway_url}/v1", ...)  # 唯一网关引用
agent = create_agent(model=llm, tools=[get_time, delete_file])
```

Agent 代码不知道网关存在——它以为在跟 OpenAI 对话。网关透明拦截 `/v1/chat/completions`。这比 A 阶段的 `/v1/intercept`（显式 API）**更强的零侵入形态**。

### 发现 2：声明级拦截（Declaration-level blocking）

LangChain `create_agent` 在第一轮请求就把**所有工具声明**发给 LLM（tools JSON）。网关在**声明阶段**检测到 `delete_file` → 直接 403，upstream 从未收到请求。

**设计权衡**：这比"调用级拦截"更严格——危险工具连声明都不允许。副作用：同一请求体里的安全工具也被连带拒绝。安全 Agent（仅 `get_time`）不受影响。这是**故意选择**：危险工具出现在 Agent 能力列表里本身就违反治理。

### 发现 3：OpenAI 兼容端点复用策略引擎

`/v1/chat/completions` 与 `/v1/intercept` 共用 `PolicyEngine` + `Storage` + fail-closed 语义（rule=None → ALLOW 默认放行，与 intercept 一致）。新增内容级检查：`_extract_tool_names()` 解析 tools + tool_calls。

## 实验拓扑

```
[LangChain Agent]  --base_url-->  [网关 :9000/v1/chat/completions]
                                     │ 策略检查 (PolicyEngine)
                                     ├─ 危险工具声明 → 403 DENY (入库)
                                     └─ 安全聊天 → 转发 → [stub LLM]
                                                        └─ OpenAI 兼容响应
```

## 测试清单

| 测试文件 | 数量 | 覆盖 |
|----------|:---:|------|
| `tests/test_integration_langchain.py` | 11 | 零侵入 AST / 工具解析 / 端点全栈 / 持久化 |
| `scripts/b1_e2e.py` | 1 (脚本) | 真实 LangChain SDK 双向端到端（venv 运行） |

## 已知限制（诚实声明）

1. **stub LLM**：上游是模拟 OpenAI 协议的 stub，非真实 GPT。真实 LLM 的响应形状可能触发 LangChain 不同的调用路径（如 tool_calls 回环），未验证
2. **AutoGen（B2）未测**：AutoGen 的 GroupChat 协议与 LangChain 不同，需单独实验
3. **声明级拦截的副作用**：危险+安全工具混合时，整个请求被拒（按设计）
4. `b1_e2e.py` 需要 venv（`pip install langchain langchain-openai`），CI 未接入（依赖体积大）

## 下一步（B2/B3）

- **B2**: AutoGen GroupChat 集成——验证多 Agent 会话经网关
- **B3**: 混合场景——LangChain + AutoGen 并存，网关统一治理
- 每项完成后更新本报告 + audit_log
