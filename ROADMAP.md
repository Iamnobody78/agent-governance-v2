# ROADMAP — governance-gateway

> 状态基准:2026-08-03 · 维护者:meta-harness 双环治理
> 约定:✅ 已交付并验证 · 🔄 进行中 · 🎯 规划中(未承诺日期)

---

## 阶段 0 — 事实核查与硬验证 ✅

| 项目 | 状态 | 说明 |
|------|:----:|------|
| tree-sitter 依赖硬锁 | ✅ | `0.21.3` + `1.5.0`,dependabot ignore 已配 |
| SQL 语法四探针验证 | ✅ | `update_statement`/`where_clause` 节点确认;`#match?` 谓词作用域缺陷实证;S1/S2 修正设计验证 |
| 虚构节点清剿 | ✅ | `table_reference`/`field`/`relation` 不存在,已排除出设计 |
| 真实拦截率基准 | ✅ | 100% 检测 / 0% 误报(15+13 载荷矩阵) |
| 基线缺口修复 | ✅ | `mkfs.*` 变体 + 重定向敏感目标 2 缺口闭环 |

## 阶段 A — 项目定位与可读性 ✅

| 项目 | 状态 | 说明 |
|------|:----:|------|
| 真实 README.md | ✅ | 从架构叙事中剥离,成为项目首页 |
| 架构文档迁移 | ✅ | `docs/architecture_narrative.md`(git mv 保历史) |
| ROADMAP.md | ✅ | 本文档 |
| 拦截率数据落盘 | ✅ | `docs/interception_benchmark.json` + 复现脚本 |

## 阶段 B — 可视化与示例 🎯

| 项目 | 状态 | 说明 |
|------|:----:|------|
| `examples/demo_self_heal.py` | 🎯 | 自愈链路演示(降级→重试→熔断) |
| `examples/browser_guard_demo.py` | 🎯 | 浏览器防护演示(URL 分类→拦截) |
| 徽章系统 | 🎯 | CI 状态 / 拦截率 / 版本徽章 |

## 阶段 C — 交付形态

### C1:容器化一键启动 🎯

| 项目 | 状态 | 说明 |
|------|:----:|------|
| `/metrics` 端点 | 🎯 | Prometheus 暴露(先于 Docker) |
| `Dockerfile` | 🎯 | 多阶段构建,python:3.11-slim |
| `docker-compose.yml` | 🎯 | 网关 + Prometheus + Grafana |

### C2:MCP 协议支持 🎯(MCP 平台化后置,独立里程碑)

| 项目 | 状态 | 说明 |
|------|:----:|------|
| MCP 服务注册 | 🎯 | 作为 MCP server 注册到 .aionui/mcp |
| 工具级治理 | 🎯 | MCP 工具调用纳入五层裁决 |

## 阶段 D — 工程完备性 🎯

| 项目 | 状态 | 说明 |
|------|:----:|------|
| Phase 1 SQL 规则 | 🎯 | `update_stmt`(无 WHERE 拦截)+ `sensitive_schema`(S1/S2 修正设计),须注册 EXPECTED_CAPTURES |
| Phase 2 Bash 深度规则 | 🎯 | 管道/命令替换/变量间接寻址等语义层 |
| Phase 3 Python 深度规则 | 🎯 | 类重绑定/装饰器逃逸/二进制协议等 |
| 许可证 | 🎯 | 选定 MIT/APACHE 并落实 LICENSE 文件 |
| CHANGELOG + 语义化版本 | 🎯 | Keep a Changelog 规范 |

## 持续运行(每轮迭代)

| 项目 | 说明 |
|------|------|
| 拦截率回归 | 每次引擎改动跑 `scripts/benchmark_interception.py` |
| Meta-Harness 内环 | 胜率连续 3 轮下降 >10% → 自动生成 3 变体验证 |
| 审计日志 | 每次交付写 `.aionui/audit_log.md` |
| 依赖升级 | dependabot 已 ignore 破坏性 tree-sitter 升级 |

---

## 变更历史

| 日期 | 变更 |
|------|------|
| 2026-08-03 | 基线:阶段 0 完成;阶段 A 完成(README/ROADMAP/数据/迁移);阶段 B/C1/C2/D 规划中 |
