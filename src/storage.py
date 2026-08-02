"""SQLite-based persistent decision storage — not an in-memory dict."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Optional


class Storage:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
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
        self.conn.commit()

    def save(self, decision: Dict) -> str:
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
        return decision["id"]

    def get_recent(self, limit: int = 50) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
        return row[0] if row else 0

    def get_by_id(self, decision_id: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

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
