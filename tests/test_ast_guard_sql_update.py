"""Phase 1 SQL rules: UPDATE-without-WHERE + sensitive-schema access.

Design verified in Stage 0 (docs/stage0_sql_grammar_verification.md):
  - update_statement node exists; where_clause child detection works
  - #match? predicate SILENTLY FAILS on bare top-level (identifier) captures
    -> S1/S2 rules hang predicates under structured parents
      (dotted_name / from_clause), verified working in PART C/D
  - table_reference/field/relation nodes do NOT exist in the grammar
"""

import pytest

from src.ast_guard import ASTGuard


@pytest.fixture()
def guard() -> ASTGuard:
    return ASTGuard()


def _blocked(guard: ASTGuard, body: dict) -> bool:
    block = guard.check_request(body)
    return block is not None and len(block.findings) > 0


def _kinds(guard: ASTGuard, body: dict) -> list:
    block = guard.check_request(body)
    if block is None:
        return []
    return sorted({f.kind for f in block.findings})


# ── AC1: UPDATE 无 WHERE → DENY ─────────────────────────────────────
class TestUpdateWithoutWhere:
    def test_update_no_where_blocked(self, guard):
        assert _blocked(guard, {"query": "UPDATE users SET status='disabled';"})

    def test_update_no_where_kind(self, guard):
        assert "destructive-update" in _kinds(
            guard, {"query": "UPDATE users SET status='disabled';"})

    def test_update_where_constant_true_allowed_by_grammar(self, guard):
        # WHERE 1=1 在语法层有 where_clause 节点 → AST 层放行（有界语义由
        # L2 YAML 层兜底）。诚实断言：AST 层不过滤恒真条件。
        assert not _blocked(guard, {"query": "UPDATE users SET active=0 WHERE 1=1;"})

    def test_update_multiple_sets_no_where(self, guard):
        assert _blocked(guard, {"query": "UPDATE t SET a=1, b=2, c=3;"})

    def test_update_delete_mix_still_danger(self, guard):
        kinds = _kinds(guard, {"query": "DELETE FROM users;"})
        assert "destructive-sql" in kinds


# ── AC2: UPDATE 有 WHERE → ALLOW ────────────────────────────────────
class TestUpdateWithWhere:
    def test_update_with_where_allowed(self, guard):
        assert not _blocked(guard, {"query": "UPDATE users SET status='disabled' WHERE id=1;"})

    def test_update_complex_where_allowed(self, guard):
        assert not _blocked(
            guard, {"query": "UPDATE orders SET total=0 WHERE user_id=5 AND status='open';"})

    def test_update_subquery_where_allowed(self, guard):
        assert not _blocked(
            guard, {"query": "UPDATE t SET x=1 WHERE id IN (SELECT id FROM s WHERE y>0);"})

    def test_update_quoted_ident_where_allowed(self, guard):
        assert not _blocked(guard, {"query": 'UPDATE "users" SET x=1 WHERE "id"=2;'})


# ── AC3: 系统敏感 schema → DENY (S1 限定名) ─────────────────────────
class TestSensitiveSchemaQualified:
    @pytest.mark.parametrize("qualified", [
        "SELECT * FROM information_schema.tables;",
        "SELECT * FROM pg_catalog.pg_tables;",
        "SELECT * FROM sqlite_master;",      # 裸名也走 S2
        "SELECT * FROM information_schema.columns WHERE table_name='users';",
        "SELECT * FROM mysql.user;",
        "SELECT * FROM sys.tables;",
    ])
    def test_sensitive_qualified_blocked(self, guard, qualified):
        assert _blocked(guard, {"query": qualified}), qualified

    def test_sensitive_kind(self, guard):
        assert "sensitive-schema-access" in _kinds(
            guard, {"query": "SELECT * FROM information_schema.tables;"})

    def test_update_sensitive_target_blocked(self, guard):
        # S3 规则: UPDATE 目标为敏感 schema 必须阻断（探针实证: 直接子节点
        # identifier 捕获, SET/WHERE 内嵌套 identifier 零误捕）
        assert _blocked(
            guard, {"query": "UPDATE sqlite_master SET sql='x' WHERE type='table';"})
        assert _blocked(
            guard, {"query": "UPDATE information_schema.tables SET x=1 WHERE y=2;"})
        # 非敏感目标不受影响
        assert not _blocked(guard, {"query": "UPDATE users SET x=1 WHERE id=1;"})
        # SET 子句含 schema 名但目标非敏感 → 零误报
        assert not _blocked(guard, {"query": "UPDATE users SET x=1, information_schema=2 WHERE id=1;"})  # noqa: E501


# ── AC4: 非敏感 schema → ALLOW (零误报) ─────────────────────────────
class TestSensitiveSchemaNonMatching:
    @pytest.mark.parametrize("benign", [
        "SELECT * FROM user_information;",   # 词根含 sensitive 但非系统 schema
        "SELECT * FROM my_schema.users;",
        "SELECT name FROM users WHERE id=1;",
        "SELECT * FROM orders JOIN users ON orders.uid = users.id;",
        "SELECT count(*) FROM sessions;",
    ])
    def test_benign_allowed(self, guard, benign):
        assert not _blocked(guard, {"query": benign}), benign

    def test_benign_schema_table_same_prefix(self, guard):
        # sys 前缀但不是系统表: sys_config 是 MySQL 系统表, 但 user_config 不是
        assert not _blocked(guard, {"query": "SELECT * FROM user_config;"})


# ── 回归: 既有 @danger 规则不受影响 ─────────────────────────────────
class TestDangerRegression:
    @pytest.mark.parametrize("danger", [
        "DROP TABLE users;",
        "DELETE FROM audit_log;",
        "TRUNCATE TABLE session_log;",
    ])
    def test_danger_still_blocked(self, guard, danger):
        assert _blocked(guard, {"query": danger}), danger

    def test_drop_database_grammar_boundary(self, guard):
        # 已知 grammar 边界: tree-sitter-sql 不支持 DROP DATABASE 方言,
        # 解析为 ERROR 节点 → AST 层无法拦截, 由 L2 YAML 规则兜底。
        # 诚实记录而非假装覆盖。
        assert not _blocked(guard, {"query": "DROP DATABASE prod;"})


# ── P1 约束: 新捕获名已注册 ────────────────────────────────────────
class TestExpectedCapturesRegistered:
    def test_new_captures_in_semantics(self, guard):
        sql_sem = guard._semantics["sql"]
        assert "update_stmt" in sql_sem
        assert "sensitive_schema" in sql_sem

    def test_no_unknown_captures_from_new_rules(self, guard):
        guard.check_request({"query": "UPDATE users SET x=1 WHERE id=2; SELECT * FROM information_schema.tables;"})
        unknown = guard.unknown_captures.get("sql", [])
        assert "update_stmt" not in unknown
        assert "sensitive_schema" not in unknown
