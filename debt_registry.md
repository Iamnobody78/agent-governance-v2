# 债务登记表 — debt_registry.md

> 规则（团队制铁律）:
> 1. 每个债务有 ID、描述、严重度、创建日期、是否阻塞
> 2. 新功能禁止引入未登记的债务
> 3. 会话结束时清点：0 阻塞债务是目标
> 4. 债务被修复 → 移入"已清偿"区并标注清偿 commit

## 活跃债务

| ID | 描述 | 严重度 | 创建日期 | 阻塞? | 来源 |
|----|------|:---:|------|:---:|------|
| DEBT-0003 | CI job 间无 `needs:` 声明（依赖分支保护） | LOW | 2026-08-03 | 否 | Reviewer A3 发现 |
## 已清偿

| ID | 描述 | 清偿 commit | 清偿日期 |
|----|------|------|------|
| DEBT-0001 | 熔断器无时间衰减（trip 后立即恢复计数，分散触发可绕过） | `0e18760` (TASK-REAL-002) | 2026-08-03 |
| DEBT-0008 | SQLite 写入失败无降级路径（直接抛异常，无内存缓存重试） | `0e18760` (TASK-REAL-002) | 2026-08-03 |
| DEBT-0005 | YAML 策略无热更新（修改 policies.yaml 需重启网关生效） | `661b77f` (TASK-REAL-001) | 2026-08-03 |
| DEBT-0006 | check_policy.py AST 规则误报含 allow/deny 子串的 dict key（如 `allow_retry`） | `661b77f` (TASK-REAL-001) | 2026-08-03 |
| DEBT-0002 | 私有 API `_is_dangerous` 耦合（policy_probe 依赖 src.main 私有符号） | `368907c` (TASK-REAL-003) | 2026-08-03 |
| DEBT-0007 | `web.run_app` 未显式 shutdown_timeout（依赖 aiohttp 默认 60s） | `368907c` (TASK-REAL-003) | 2026-08-03 |
| DEBT-0009 | `_pending` 内存缓存无上限（长时降级时内存占用风险） | `368907c` (TASK-REAL-003) | 2026-08-03 |
| DEBT-0010 | `flush_pending()` 重试时机未明确（建议 main.py 启动/关闭时触发） | `368907c` (TASK-REAL-003) | 2026-08-03 |
| DEBT-0004 | chat 端点无流式（stream:true 客户端 TTFT 退化 + SSE 语义丢失） | `3aea7d2` (TASK-REAL-004) | 2026-08-03 |

