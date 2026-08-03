"""Storage degraded-mode tests (DEBT-0008).

New contract: save() must not raise on sqlite errors — instead it buffers
the decision in an in-memory list with a _cached_at timestamp, and
flush_pending() retries the write later.

NOTE: sqlite3.Connection.execute is read-only (cannot be patch.object'd),
so we substitute a FakeConn whose execute() raises OperationalError.
"""

import sqlite3
import tempfile

from src.storage import Storage


class FakeConn:
    """Connection stand-in whose execute() always raises (degraded disk)."""

    def __init__(self, raise_on_execute=True):
        self._raise = raise_on_execute
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._raise:
            raise sqlite3.OperationalError("disk I/O error")
        return FakeCursor()

    def commit(self):
        pass

    def close(self):
        pass


class FakeCursor:
    def fetchall(self):
        return []

    def fetchone(self):
        return None


def make_storage() -> Storage:
    return Storage(db_path=tempfile.mktemp(suffix=".db"))


def make_decision() -> dict:
    return {
        "id": "test-id-0008",
        "verdict": "ALLOW",
        "reason": "test",
        "matched_rule": None,
        "timestamp": "2026-08-03T00:00:00+00:00",
        "path": "/api/chat",
        "method": "POST",
        "agent_id": None,
    }


class TestStorageDegradedMode:
    def test_save_success(self):
        s = make_storage()
        decision = make_decision()
        result = s.save(decision)
        assert result == decision["id"]
        assert s.pending_count() == 0
        s.conn.close()

    def test_save_failure_buffers_in_memory(self):
        s = make_storage()
        s.conn = FakeConn()  # execute() raises OperationalError
        decision = make_decision()

        # MUST NOT raise (DEBT-0008: gateway must not fail)
        result = s.save(decision)

        assert result == decision["id"]
        assert s.pending_count() == 1
        s.conn.close()

    def test_pending_entry_has_cached_at(self):
        s = make_storage()
        s.conn = FakeConn()
        decision = make_decision()

        s.save(decision)

        assert s._pending[0]["_cached_at"]
        # timestamp is ISO-format string
        assert "T" in s._pending[0]["_cached_at"]
        s.conn.close()

    def test_flush_pending_success(self):
        s = make_storage()
        decision = make_decision()

        # Phase 1: degraded disk → buffered
        s.conn = FakeConn()
        s.save(decision)
        assert s.pending_count() == 1

        # Phase 2: disk recovers → _init() rebuilds a healthy connection,
        # flush_pending persists the buffered decision.
        s._init()
        flushed = s.flush_pending()
        assert flushed == 1
        assert s.pending_count() == 0
        recent = s.get_recent(limit=10)
        assert any(
            r.get("id") == decision["id"] for r in recent
        ), "flushed decision must be persisted"
        s.conn.close()

    def test_flush_keeps_failed_entries(self):
        s = make_storage()
        s.conn = FakeConn()
        decision = make_decision()

        s.save(decision)

        # conn.execute still broken → flush fails, entry stays buffered
        flushed = s.flush_pending()

        assert flushed == 0
        assert s.pending_count() == 1
        s.conn.close()
