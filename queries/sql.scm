; sql.scm — 危险 SQL 语句模式（S-expression 查询，零正则）
;
; 捕获名语义:
;   @danger            — 破坏性 DDL/DML（数据销毁类）
;   @update_stmt       — UPDATE 语句（Python 侧后处理: 无 WHERE 子句 → 阻断）
;   @sensitive_schema  — 系统敏感 schema 访问（限定名 S1 + 裸名 S2 双规则）
;
; ── 破坏性语句（DROP/DELETE/TRUNCATE）—— 任何出现都触发阻断 ──────────
; 注: 多语句批次注入不在 AST 层判定（sql grammar 无统一根节点类型,
; 跨方言结构差异大），由 L2 YAML 规则 + 上下文分析兜底。
[(drop_statement) (delete_statement) (truncate_statement)] @danger

; ── UPDATE 语句 —— 无 WHERE = 全表更新（数据丢失风险）───────────────
; 捕获整个 update_statement，Python 侧遍历 children 检查 where_clause:
;   有 where_clause → ALLOW（有界更新）
;   无 where_clause → DENY（全表覆盖）
(update_statement) @update_stmt

; ── 系统敏感 schema 访问 ──────────────────────────────────────────────
; S1: 限定名（dotted_name）—— information_schema.tables / pg_catalog.pg_tables
;     谓词挂在结构化父节点下（阶段 0 PART C 实证: 顶层裸 identifier 谓词
;     静默失效，结构化子节点下生效）
(from_clause
  (dotted_name
    (identifier) @sensitive_schema
    (#match? @sensitive_schema "^(information_schema|pg_catalog|sqlite_master|mysql|sys|performance_schema|pg_toast)$")))

; S2: 裸表名（单 identifier）—— SELECT * FROM sqlite_master
;     阶段 0 PART D 实证: from_clause 子节点下谓词生效
(from_clause
  (identifier) @sensitive_schema
  (#match? @sensitive_schema "^(information_schema|pg_catalog|sqlite_master|mysql|sys|performance_schema|pg_toast)$"))

; S3: UPDATE 目标表为敏感 schema —— UPDATE sqlite_master SET ...
;     探针实证: (update_statement (identifier)) 无通配符 → 仅匹配直接子节点
;     （目标表），SET/WHERE 内嵌套 identifier 零误捕。
(update_statement
  (identifier) @sensitive_schema
  (#match? @sensitive_schema "^(information_schema|pg_catalog|sqlite_master|mysql|sys|performance_schema|pg_toast)$"))
