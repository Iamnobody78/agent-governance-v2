# 🧬 Teams 代理团队协作协议 v2.0

> **定位**：让 2-5 个 AionUI 子代理组成自治团队，并行处理 agent-governance 项目的开发、测试、审查、归档任务。
>
> **核心约束（来自实验）**：
> - 单代理工作量 ≤2 文件、≤5 维度
> - 单次 Spawn ≤3 代理并行（4+ 会资源竞争超时）
> - **子代理之间无法互相通信** → 必须用两阶段 Spawn（见 §2.4）

---

## 一、角色定义

| 角色 | 职责 | 允许写入 | 典型任务 |
|------|------|:--:|------|
| **Builder** 🛠️ | 生成/修改源代码 | `src/`, `config/` | 实现新模块、修复 bug、重构 |
| **Tester** 🧪 | 编写测试、运行测试 | `tests/` | 补充测试用例、修复 flaky test |
| **Reviewer** 🔍 | 审查代码、审计安全 | 只读（输出报告） | 安全审计、架构合规检查 |
| **Archivist** 📁 | 更新文档、记录日志 | `*.md`, `.aionui/` | 更新 CHANGELOG、写审查报告 |

**规则**：
- Builder 和 Reviewer 不能是同一代理（不可自我审查）。
- 每次变更必须经过"Builder → Reviewer → Archivist"三阶段闭环。
- 如果团队只有 2 个代理：省略 Archivist 角色，Reviewer 兼任。
- **Spawn 子代理是"哑执行者"**：它们只执行明确指令并输出结果，不做跨代理协调——协调永远是 Coordinator（主代理）的职责。

---

## 二、任务分配协议

### 2.1 任务模板

Coordinator 使用以下模板分配任务：

```markdown
## 任务分配 — {{TASK_ID}}

### 背景
[一句话：为什么需要这个任务]

### 优先级
P0 / P1 / P2 / P3

### 文件分配表（防撞车）
| 文件 | 负责代理 | 角色 |
|------|----------|------|
| src/xxx.py | Builder-1 | 修改 |
| tests/test_xxx.py | Tester-1 | 新增 |

### 验收标准
- [ ] 测试通过 (pytest -q)
- [ ] GATE 1-4 全部通过
- [ ] Reviewer 输出 PASS
- [ ] Archivist 记录到 CHANGELOG

### 截止时间
[时间窗口]
```

### 2.2 粒度限制（强制）

| 约束 | 值 | 来源 |
|------|:--:|------|
| 单代理最大文件数 | 2 | 实验数据：3 文件 → 超时 |
| 单代理最大审查维度 | 5 | 实验数据：超过 5 维度 → 超时 |
| 单次 Spawn 最大并行代理数 | 3 | 实验数据：4+ 代理 → 资源竞争 |
| 单代理最大输出行数 | 100 | **Spawn 输出 4096 token 截断**，超长会被切掉 |

### 2.3 两阶段 Spawn 架构（关键）

**由于 Spawn 子代理之间无法互相通信，禁止在单次 Spawn 中构建跨代理依赖链。**

```
阶段 1 — Spawn #1（并行，无依赖）
┌─────────────┬─────────────┬─────────────┐
│  Builder-1  │  Builder-2  │  Tester-1   │
│  写 src/     │  写 config/ │  写 tests/  │
└──────┬──────┴──────┬──────┴──────┬──────┘
       └─────────────┼─────────────┘
                     ▼
       Coordinator 验证层（必须执行，不可跳过）
       ├── git diff 检查文件变更
       ├── python -m pytest tests/ -q
       └── python scripts/check_test_quality.py
                     ▼
阶段 2 — Spawn #2（串行，读最终文件）
       ┌─────────────┐
       │  Reviewer   │
       │  读最终文件  │ ← 独立读取，不依赖 Builder 的交接块
       └──────┬──────┘
              ▼
       Coordinator 汇总
       ├── 通过 → git add + commit + push
       ├── REJECT → 分配回 Builder 重做（新 Spawn）
       └── 记录 → Archivist 任务（或 Coordinator 兼任）
```

**为什么必须两阶段**：
- 阶段 1 的 Builder 们互不依赖 → 可安全并行
- 阶段 2 的 Reviewer 需要看 Builder 的**最终落盘文件** → 必须等阶段 1 完成后单独启动
- 单次 Spawn 内传"交接块"给另一个子代理是**不可能的**（独立上下文）

### 2.4 结果汇总格式

子代理输出必须精简（≤100 行），格式固定：

```markdown
## {{ROLE}} 输出 — {{TASK_ID}}

### 结果
PASS / FAIL / REJECT

### 变更摘要
- 文件: `src/xxx.py` (+12, -5)
- 关键变更: [1-2 句话]

### 待 Coordinator 验证
1. [请跑 pytest 确认 xxx]
2. [请检查 GATE 1 是否通过]

### 已知限制
- [未覆盖的边界情况，如有]
```

---

### 2.5 调度层第一阶段：自动接力循环（v0.2.2+，AUDIT-0010）

> **目标**：Builder → Reviewer 接力由 Coordinator **自动驱动**，用户零介入。
> 验证实验：TASK-SCHED-001（Builder 写 src/time_utils.py + tests → Reviewer 独立审查 → PASS，1 轮完成）。

**架构约束（实测确认，勿违反）**：
1. Spawn schema 明确禁止 "shared state or sequential coordination" → **子代理之间无法互相对话/嵌套 Spawn**
2. 协调永远是 Coordinator（主代理）职责 → "自动接力" = Coordinator 在单次会话内连续执行 Builder→Reviewer→(修复→复审) 循环，直到 PASS 或达 MAX_ROUNDS
3. 共享上下文 = **工作区文件系统**（work/<TASK_ID>/ 是接力总线）

**状态机**（.aionui/scheduler/relay_state.json）：
- Coordinator 创建任务时初始化；每轮 Builder/Reviewer 完成后追加 history；终态 DONE_PASS / DONE_REJECT
- 字段: task_id / status / round / max_rounds / builder_output / reviewer_verdict / history[]

**接力循环**：
`
BUILD(n) → 验证产物落盘 → REVIEW(n) → 读 verdict
  ├─ PASS  → 终态 DONE_PASS（可提交）
  ├─ REJECT → BUILD(n+1)（把 verdict 的 Required fixes 原样传入 Builder）→ REVIEW(n+1)
  └─ n >= MAX_ROUNDS → DONE_REJECT（升级人工）
`

**关键教训（TASK-SCHED-001 实测）**：
1. **先落盘原则**：Reviewer v1 被 Spawn 截断（2 turns）导致 verdict 未写入 → 接力中断。
   修正：Reviewer prompt 强制 "STEP 3 = 立即写 verdict 文件，即使有未决疑点"，深查在落盘之后。
   所有**关键产物**（verdict、报告）必须"先落盘、后完善"，不得依赖子代理完整跑完。
2. **Builder 必须自证**：测试命令 + 真实输出写在 builder_output.md，Reviewer 独立重跑验证（防口头通过）。
3. **断言 vs 产物**：接力判断只认落盘文件（verdict 存在且首行含 PASS/REJECT），不认子代理的 stdout 摘要。

**文件分配**（防撞车，沿用 §2.2）：
- Builder 写 src/、	ests/（≤2 文件）+ work/<TASK>/builder_output.md
- Reviewer 只写 work/<TASK>/reviewer_verdict.md（其余全只读）
## 三、协作协议

### 3.1 Coordinator 验证铁律

| 铁律 | 说明 |
|------|------|
| **不可信任子代理的自报结果** | 子代理说"测试通过"不等于测试通过。Coordinator 必须自己跑 `pytest -q` |
| **不可跳过 Reviewer** | 任何代码变更必须经过独立 Reviewer 审查 |
| **不可并行分配冲突文件** | 同一文件只允许一个 Builder 写（见文件分配表） |
| **GATE 未过不提交** | 4 门控任何一个失败 → 打回重做 |

### 3.2 冲突解决

如果两个 Builder 修改同一文件（分配表被违反）：
1. Coordinator 标记冲突。
2. 保留较早提交的变更，通知后提交的 Builder 基于最新版本重做。
3. 如果无法合并，放弃该文件的最新变更，仅保留经 Reviewer 通过的部分。

### 3.3 失败处理

| 失败类型 | 处理方式 |
|----------|----------|
| 单代理超时 (>5min) | Coordinator 重新分配同任务给新代理 |
| 子代理输出被截断 | 要求重跑，输出 ≤100 行 |
| 子代理假报"测试通过" | Coordinator 自己跑测试发现 → 标记该代理不可信，下次换新代理 |
| Reviewer REJECT | 分配回原 Builder 重做（新 Spawn 阶段 1） |
| GATE 失败 | Coordinator 直接修复（小问题）或分配 Builder（大问题） |

---

## 四、与现有协议的集成

```
Teams 协作协议 ← 本协议
    │
    ├── 触发条件:
    │   - 用户说 "用团队模式" / "@team start"
    │   - 任务涉及 3+ 文件修改
    │   - 需要并行审查
    │
    ├── 上游依赖:
    │   - 主治医师健康诊断 (每次会话启动)
    │   - CI 四门控 (每次提交前)
    │
    └── 下游输出:
        - Archivist → CHANGELOG.md
        - Archivist → .aionui/audit_log.md
        - Reviewer → CRITIQUE_V*.md (如有发现)
```

---

## 五、Coordinator 启动序列

当主代理以 Coordinator 角色启动 Teams 协作时，执行以下序列：

```
1. 主治医师健康诊断
   └── 输出当前项目健康度 → 决定优先处理的风险

2. 任务拆解
   └── 按粒度限制 (<2 files/<5 dims) 拆解待办任务
   └── 生成文件分配表（防撞车）

3. 阶段 1: 并行执行（Spawn #1）
   └── Builder/Tester 并行，最多 3 个，超时 5min

4. Coordinator 验证层（不可跳过）
   ├── git diff 检查
   ├── python -m pytest tests/ -q
   └── python scripts/check_test_quality.py

5. 阶段 2: 独立审查（Spawn #2）
   └── Reviewer 读最终文件，输出 PASS/REJECT

6. 汇总与提交
   ├── 通过 → git add + commit + push
   ├── REJECT → 回步骤 3（新 Spawn 重做）
   └── 记录 → Archivist 写入 CHANGELOG + audit_log
```

---

## 六、快速启动命令

| 命令 | 效果 |
|------|------|
| `@team start` | 启动 Teams 协作模式（执行启动序列） |
| `@team review <文件>` | 派 Reviewer 审查指定文件（阶段 2） |
| `@team build <任务描述>` | 派 Builder 实现功能（阶段 1） |
| `@team test <模块名>` | 派 Tester 补测试（阶段 1） |
| `@team status` | Coordinator 输出团队当前状态 |
| `@team handoff` | 输出交接块到 `.aionui/teams/handoff_YYYYMMDD.md`，供下一个会话续接 |

---

## 七、工作空间约定

| 位置 | 用途 |
|------|------|
| `.aionui/teams/` | 团队运行状态、handoff 文件 |
| `.aionui/teams/handoff_YYYYMMDD.md` | 每日交接块（`@team handoff` 写入） |
| `.aionui/audit_log.md` | 审查记录（永久保留） |
| `CHANGELOG.md` | 版本记录（Archivist 维护） |

---

*本协议由 agent-governance v2 实验生成。v1.0 于 2026-08-03 首版，v2.0 修正"子代理无法互相通信"架构缺陷后升级。*
*每次 Spawn 实验后更新粒度限制参数。*

