# 🧬 Teams 代理团队协作协议 v1.0

> **定位**：让 2-5 个 AionUI 子代理组成自治团队，并行处理 agent-governance 项目的开发、测试、审查、归档任务。
>
> **核心约束（来自实验）**：单代理工作量 ≤2 文件、≤5 维度。超过此粒度，拆分为多个子代理。

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

---

## 二、任务分配协议

### 2.1 任务模板

发起代理（Coordinator）使用以下模板分配任务：

```markdown
## 任务分配 — {{TASK_ID}}

### 背景
[一句话：为什么需要这个任务]

### 优先级
P0 / P1 / P2 / P3

### 代理分配
| 角色 | 代理 ID | 任务摘要 | 文件范围 |
|------|---------|----------|----------|
| Builder-1 | [name] | [what to build] | src/xxx.py |
| Tester-1 | [name] | [what to test] | tests/test_xxx.py |
| Reviewer | [name] | [what to review] | [文件列表] |

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
| 最大并行代理数 | 3 | 实验数据：$4+$ 代理 → 资源竞争 |
| 单代理最大输出行数 | 300 | 控制 token 消耗 |

### 2.3 并行与顺序策略

```
          ┌──────────┐
          │Coordinator│ (主代理，用户在对话中)
          └─────┬────┘
                │
       ┌────────┼────────┐
       │        │        │
       ▼        ▼        ▼
   Builder-1  Builder-2  Tester-1     ← 可并行（无依赖）
       │        │        │
       └────────┼────────┘
                │
                ▼
           Reviewer                       ← 串行（依赖前序）
                │
                ▼
           Archivist                      ← 串行（依赖审查）
```

---

## 三、协作协议

### 3.1 交接格式

当一个代理完成工作后，输出以下格式的交接块，供下一个代理读取：

````markdown
## 🔄 交接块 — {{ROLE}} → {{NEXT_ROLE}}

### 变更摘要
- 文件: `src/main.py` (+15, -8)
- 描述: 修复熔断器时间衰减
- Commit: `abc1234`

### 变更内容
```python
# 修改的关键代码
```

### 已知限制
- [任何未覆盖的边界情况]

### 测试建议
- [指导下一个代理关注什么]
````

### 3.2 冲突解决

如果两个 Builder 修改同一文件：
1. Coordinator（主代理）负责合并冲突。
2. 如果合并矛盾，优先保留较早提交的变更，并通知后提交的 Builder 重新基于最新版本修改。

### 3.3 失败处理

| 失败类型 | 处理方式 |
|----------|----------|
| 单代理超时 (>5min) | Coordinator 重新分配同任务给新代理 |
| 单代理错误输出 | Reviewer 标记 REJECT，Coordinator 重新分配 |
| 测试失败 | Tester 输出失败日志，Coordinator 分配给 Builder 修复 |
| Reviewer REJECT | Coordinator 分配给原 Builder 重做 |

---

## 四、与现有协议的集成

```
Teams 协作协议 ← 本协议
    │
    ├── 触发条件:
    │   - 用户说 "用团队模式"
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

3. 代理分配
   └── 按角色分配任务 → Builder / Tester / Reviewer / Archivist

4. 并行执行（Spawn）
   └── 最多 3 代理并行，超时 5min

5. 结果汇总
   └── 收集交接块 → 合并 → 提交

6. 审查闭环
   └── Builder → Reviewer → 通过/打回 → 重做或归档

7. 记录
   └── Archivist 写入 CHANGELOG + audit_log
```

---

## 六、快速启动命令

| 命令 | 效果 |
|------|------|
| `@team start` | 启动 Teams 协作模式 |
| `@team review <文件>` | 派 Reviewer 审查指定文件 |
| `@team build <任务描述>` | 派 Builder 实现功能 |
| `@team test <模块名>` | 派 Tester 补测试 |
| `@team status` | Coordinator 输出团队当前状态 |
| `@team handoff` | 输出当前会话的完整交接块，供下一个 Coordinator 续接 |

---

*本协议由 agent-governance v2 实验生成。首次部署于 2026-08-03。*
*每次 Spawn 实验后更新粒度限制参数。*
