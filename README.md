# governance-gateway

**非侵入式 Sidecar/Proxy 智能体治理网关** — 在 Agent 与 LLM 之间建立可审计的策略裁决层,以 AST 级语义分析拦截危险请求,并内置**策略建议器**(Policy Suggester)做**策略级**持续优化(诚实边界:生成策略候选,不修改核心引擎代码;理念源自 Meta-Harness 研究框架,但仅实现适配层能力)。

> 架构叙事与演进史见 [`docs/architecture_narrative.md`](docs/architecture_narrative.md)
> 现行架构权威参考见 [`docs/architecture.md`](docs/architecture.md)

---

## ✨ 核心特性

| 能力 | 说明 |
|------|------|
| 🛡️ **五层裁决** | `ALLOW(200)` / `ALLOW_WITH_WARNING` / `ESCALATE(202)` / `DENY(403)` / `SUSPEND(403)` |
| 🔬 **AST 语义门** | 基于 tree-sitter 的代码级分析(锁定 `0.21.3` + `1.5.0`),非字符串匹配 |
| 🌐 **三语言覆盖** | Python(`eval`/`exec`/动态导入)、Bash(破坏性命令/标志/重定向)、SQL(危险 DDL/敏感 Schema) |
| 🧠 **治理大脑** | YAML 声明式策略引擎 + 值表正则内嵌 .scm(零 Python 硬编码) |
| 🔄 **策略级自进化** | 策略建议器:内环生成策略候选 + Pareto 前沿裁决(只读 storage、不改核心引擎——诚实边界,非完整 Harness 工程自动化) |
| 📊 **全链路审计** | 每次请求的裁决轨迹落盘,`/v1/traces` 可回溯 |
| 🧪 **CI 质量门** | 8 道 GATE(单测 / lint / 扫描器 / E2E / HIL)全绿 |

## 📈 真实拦截率

基于**生产路径**(`PolicyEngine.evaluate` + `ASTGuard`)对 20 个恶意 + 15 个良性载荷矩阵实测(2026-08-04,含 SQL 恶意×5):

```
  检测率 (Recall)       : 20/20 = 100%
  误报率 (False Pos.)   : 0/15  = 0%
  精确率 (Precision)    : 20/20 = 100%
```

> 数据文件:`docs/interception_benchmark.json` | 复现:`python scripts/benchmark_interception.py`
> 此基准曾捕获 2 个真实拦截缺口(`mkfs.ext4` 变体、`> /etc/passwd` 重定向),已修复并回归验证。

## 🚀 快速开始

### 方式 1:本地运行

```bash
pip install -e .
# 启动网关(默认 :8000)
python -m src.main
```

### 方式 2:Docker(规划中,见 ROADMAP)

```bash
docker compose up --build   # 阶段 C1 后可用
```

### 健康检查

```bash
curl http://localhost:8000/health
```

## 🔍 使用示例

```bash
# 恶意:SQL 无 WHERE 的 DELETE —— 被 AST 门拦截
curl -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"run query"}],"sql":{"query":"DELETE FROM users;"}}'

# 良性:带 WHERE 的 UPDATE —— 放行
curl -X POST http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"update"}],"sql":{"query":"UPDATE users SET active=0 WHERE id=1;"}}'
```

## 🏗️ 架构总览

```
┌─────────────┐     ┌─────────────────────────────────────────┐     ┌──────────┐
│  Agent / LLM │ ──▶ │        governance-gateway (sidecar)      │ ──▶ │  Upstream │
└─────────────┘     │                                         │     └──────────┘
                    │  L1 基础设施 │ L2 核心网关 │ L3 治理大脑  │
                    │  L4 批判智能体 │ L5 策略级自进化(适配层) │
                    └─────────────────────────────────────────┘
```

五层架构细节见 [`docs/architecture.md`](docs/architecture.md)。

## 📚 文档索引

| 文档 | 内容 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 现行架构权威参考 |
| [docs/architecture_narrative.md](docs/architecture_narrative.md) | v1→v2 演进叙事与 ADR |
| [docs/OPERATIONS_MANUAL.md](docs/OPERATIONS_MANUAL.md) | 运维手册(AC1-10 验收) |
| [docs/stage0_sql_grammar_verification.md](docs/stage0_sql_grammar_verification.md) | 阶段 0:SQL 语法硬验证 |
| [docs/META_HARNESS_FUSION_REPORT.md](docs/META_HARNESS_FUSION_REPORT.md) | 策略建议器融合报告(理念源自 Meta-Harness,能力边界见报告 §诚实边界) |
| [docs/CERTIFICATION.md](docs/CERTIFICATION.md) | 认证与验收状态 |
| [ROADMAP.md](ROADMAP.md) | 路线图 |
| [CRITIQUE_V2.md](CRITIQUE_V2.md) | 第二轮外部批判 + 逐条回应(含整改 deadline) |

## 🛠️ 技术栈

- **Python ≥ 3.10** / FastAPI / Uvicorn
- **tree-sitter 0.21.3**(硬锁)+ tree-sitter-languages 1.5.0(硬锁)
- **PyYAML** 策略引擎 · **pytest** 测试(904 用例通过 + 1 跳过)· **Ruff** lint 零错误
- **GitHub Actions** CI 3 门(quality/policy/critic)+ all-gates 聚合 + dependabot(忽略破坏性 tree-sitter 升级)

## 🩺 维护状态

> **研究型项目,非生产级软件。** 本仓库由单一治理智能体在迭代开发中维护,发布节奏为"裁决驱动的快照"而非固定 cadence。

| 维度 | 状态 |
|------|------|
| 活跃开发 | ✅ 持续(最近快照 v1.42.0-stagea,2026-08-05) |
| 兼容性承诺 | ⚠️ 无 LTS/API 冻结;tree-sitter 锁版为主动决策(见 dependabot ignore) |
| 已知边界 | 性能上限(见下)、GPG/ED25519 不兼容(见 CERTIFICATION.md)、DROP DATABASE 语法边界(见 stage0 报告) |
| 商业支持 | ❌ 无 SLA/无企业支持;社区协作经 GitHub Issues/Discussions |
| 变更跟踪 | ROADMAP 变更历史 + CHANGELOG(规划中,阶段 D) |

### ⚡ 性能上限(公开声明)

本项目为 Python **单进程同步裁决引擎**(非异步代理管线),以下为诚实边界而非缺陷:

- **吞吐**: 裁决路径为同步 CPU 计算(AST 解析 + 策略匹配),高并发下受 GIL 约束;基准见 `docs/OPERATIONS_MANUAL.md`(测试环境实测为准)
- **规模**: 策略 YAML 与 .scm 查询为线性匹配,数千条规则场景需预编译/索引优化(当前未实现)
- **审计**: 存储层为 WAL SQLite,决策轨迹在高写入速率下有 IO 瓶颈;流式消费为 v2 候选
- **架构选择**: 侧车/代理拦截天然引入一跳延迟;已在设计中保持裁决 < 毫秒级,未做多进程/多语言扩展

## 📄 许可证

MIT(待定 —— 见 ROADMAP 阶段 D)
