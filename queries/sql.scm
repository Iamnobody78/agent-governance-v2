; sql.scm — 危险 SQL 语句模式（S-expression 查询，零正则）
;
; 捕获名语义:
;   @danger — 破坏性 DDL/DML（数据销毁类）
;
; 破坏性语句（DROP/DELETE/TRUNCATE）—— 任何出现都触发阻断。
; 注: 多语句批次注入不在 AST 层判定（sql grammar 无统一根节点类型,
; 跨方言结构差异大），由 L2 YAML 规则 + 上下文分析兜底。
[(drop_statement) (delete_statement) (truncate_statement)] @danger
