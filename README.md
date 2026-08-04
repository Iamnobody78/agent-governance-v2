# governance-gateway

**非侵入式 Sidecar/Proxy 智能体治理网关** — 在 Agent 与 LLM 之间建立可审计的策略裁决层,以 AST 级语义分析拦截危险请求,并基于 Meta-Harness 适配层做**策略级**持续优化(诚实边界:生成策略候选,不修改核心引擎代码)。

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
| 🔄 **策略级自进化** | Meta-Harness 适配层:内环生成策略候选 + Pareto 前沿裁决(只读 storage、不改核心引擎——诚实边界) |
| 📊 **全链路审计** | 每次请求的裁决轨迹落盘,`/v1/traces` 可回溯 |
| 🧪 **CI 质量门** | 8 道 GATE(单测 / lint / 扫描器 / E2E / HIL)全绿 |

## 📈 真实拦截率

基于**生产路径**(`PolicyEngine.evaluate` + `ASTGuard`)对 15 个恶意 + 13 个良性载荷矩阵实测(2026-08-03):

```
  检测率 (Recall)       : 15/15 = 100%
  误报率 (False Pos.)   : 0/13  = 0%
  精确率 (Precision)    : 15/15 = 100%
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
| [docs/META_HARNESS_FUSION_REPORT.md](docs/META_HARNESS_FUSION_REPORT.md) | Meta-Harness 双环融合报告 |
| [docs/CERTIFICATION.md](docs/CERTIFICATION.md) | 认证与验收状态 |
| [ROADMAP.md](ROADMAP.md) | 路线图 |

## 🛠️ 技术栈

- **Python ≥ 3.10** / FastAPI / Uvicorn
- **tree-sitter 0.21.3**(硬锁)+ tree-sitter-languages 1.5.0(硬锁)
- **PyYAML** 策略引擎 · **pytest** 测试(573 用例通过)· **Ruff** lint 零错误
- **GitHub Actions** CI 8 门 + dependabot(忽略破坏性 tree-sitter 升级)

## 📄 许可证

MIT(待定 —— 见 ROADMAP 阶段 D)
