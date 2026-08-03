"""SQLite-based persistent decision storage — not an in-memory dict."""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional

PENDING_MAX = 1000  # DEBT-0009: cap on degraded-mode in-memory buffer (memory safety)
logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        # v0.2.2 (external critique #3.1): saves now run via asyncio.to_thread
        # on the event loop; the single shared connection (check_same_thread=False)
        # must be serialized across threads → guard every operation with a lock.
        self._lock = threading.Lock()
        self._pending: List[Dict] = []  # DEBT-0008: degraded-mode in-memory buffer
        self._init()

    def _init(self) -> None:
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                verdict TEXT NOT NULL,
                reason TEXT NOT NULL,
                matched_rule TEXT,
                timestamp TEXT NOT NULL,
                path TEXT NOT NULL,
                method TEXT NOT NULL,
                agent_id TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ts ON decisions(timestamp DESC)
        """)
        # DEBT-0011: persisted circuit-breaker state (single-row KV) so a gateway
        # restart cannot reset escalate counters and bypass the cooldown window.
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS breaker_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def save(self, decision: Dict) -> str:
        try:
            with self._lock:
                self.conn.execute(
                    """INSERT INTO decisions (id, verdict, reason, matched_rule, timestamp, path, method, agent_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        decision["id"],
                        decision["verdict"],
                        decision["reason"],
                        decision.get("matched_rule"),
                        decision["timestamp"],
                        decision["path"],
                        decision["method"],
                        decision.get("agent_id"),
                    ),
                )
                self.conn.commit()
        except sqlite3.Error:
            # DEBT-0008: degraded mode — buffer decision in memory with timestamp;
            # flush_pending() retries later. Do NOT raise (gateway must not fail).
            entry = dict(decision)
            entry["_cached_at"] = datetime.now(timezone.utc).isoformat()
            with self._lock:
                self._pending.append(entry)
                if len(self._pending) > PENDING_MAX:  # DEBT-0009: drop oldest, keep bounded
                    dropped = self._pending.pop(0)
                    logger.warning("degraded buffer full (%d): dropping oldest decision %s", PENDING_MAX, dropped.get("id"))
        return decision["id"]

    def flush_pending(self) -> int:
        """DEBT-0008: retry writing buffered decisions. Returns number flushed."""
        flushed = 0
        with self._lock:
            remaining = []
            for entry in self._pending:
                try:
                    self.conn.execute(
                        """INSERT INTO decisions (id, verdict, reason, matched_rule, timestamp, path, method, agent_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            entry["id"],
                            entry["verdict"],
                            entry["reason"],
                            entry.get("matched_rule"),
                            entry["timestamp"],
                            entry["path"],
                            entry["method"],
                            entry.get("agent_id"),
                        ),
                    )
                    self.conn.commit()
                    flushed += 1
                except sqlite3.Error:
                    remaining.append(entry)
            self._pending = remaining
        return flushed

    def pending_count(self) -> int:
        """DEBT-0008: number of decisions buffered in degraded mode."""
        with self._lock:
            return len(self._pending)

    def get_recent(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def count(self) -> int:
        with self._lock:
            row = self.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
        return row[0] if row else 0

    def get_by_id(self, decision_id: str) -> Optional[Dict]:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM decisions WHERE id = ?", (decision_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def save_breaker_state(self, count: int, last_escalate: float, tripped_until: float) -> None:
        """DEBT-0011: persist circuit-breaker state across restarts."""
        state = {"count": count, "last_escalate": last_escalate, "tripped_until": tripped_until}
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT OR REPLACE INTO breaker_state (key, value) VALUES (?, ?)",
                    ("breaker", json.dumps(state)),
                )
                self.conn.commit()
        except sqlite3.Error:
            logger.warning("save_breaker_state failed (degraded): state not persisted")

    def load_breaker_state(self) -> Dict:
        """DEBT-0011: restore breaker state at startup; defaults if absent."""
        default = {"count": 0, "last_escalate": 0.0, "tripped_until": 0.0}
        try:
            with self._lock:
                row = self.conn.execute(
                    "SELECT value FROM breaker_state WHERE key = ?", ("breaker",)
                ).fetchone()
        except sqlite3.Error:
            return default
        if not row:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def _row_to_dict(row) -> Dict:
        return {
            "id": row[0],
            "verdict": row[1],
            "reason": row[2],
            "matched_rule": row[3],
            "timestamp": row[4],
            "path": row[5],
            "method": row[6],
            "agent_id": row[7],
        }

    def close(self) -> None:
        if self.conn:
            self.conn.close()
