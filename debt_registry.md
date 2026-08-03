# 债务登记表 — debt_registry.md

> 规则（团队制铁律）:
> 1. 每个债务有 ID、描述、严重度、创建日期、是否阻塞
> 2. 新功能禁止引入未登记的债务
> 3. 会话结束时清点：0 阻塞债务是目标
> 4. 债务被修复 → 移入"已清偿"区并标注清偿 commit

## 活跃债务

| ID | 描述 | 严重度 | 创建日期 | 阻塞? | 来源 |
|----|------|:---:|------|:---:|------|
| DEBT-0001 | 熔断器 reset-on-trip 无时间衰减（攻击者可分散触发，需 9 次 ESCALATE 才触发） | LOW | 2026-08-03 | 否 | AUDIT-0005 残余 |
| DEBT-0002 | 私有 API `_is_dangerous` 耦合（policy_probe 依赖 src.main 私有符号） | LOW | 2026-08-03 | 否 | AUDIT-0005 审查 |
| DEBT-0003 | CI job 间无 `needs:` 声明（依赖分支保护） | LOW | 2026-08-03 | 否 | Reviewer A3 发现 |
| DEBT-0004 | `_proxy_forward` 请求体一次性加载（无流式） | LOW | 2026-08-03 | 否 | AUDIT-0005 审查 |
| DEBT-0005 | YAML 策略无热更新（修改 policies.yaml 需重启网关生效） | LOW | 2026-08-03 | 否 | 外部批判 2.3 |
| DEBT-0006 | check_policy.py AST 规则可能误报含 allow/deny 的普通 dict key（如 `allow_retry`） | LOW | 2026-08-03 | 否 | 外部批判 6.1 |
| DEBT-0007 | `web.run_app` 未显式 shutdown_timeout（依赖 aiohttp 默认 60s，属调参偏好非缺陷） | LOW | 2026-08-03 | 否 | 外部批判 1.5 |
| DEBT-0008 | 测试未覆盖 SQLite 写入失败降级路径 | LOW | 2026-08-03 | 否 | 外部批判 5.3 |

## 已清偿

| ID | 描述 | 清偿 commit | 清偿日期 |
|----|------|------|------|
| （无） | | | |
