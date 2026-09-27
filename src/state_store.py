"""
src/state_store.py - SQLite state persistence with WAL mode, atomic counters,
and session lifecycle tracking for Jules repository audits.
"""

from datetime import datetime, timezone
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jules_state_store")


class StateStore:
    def __init__(self, db_path: str = "jules_audit.db"):
        self.db_path = db_path
        self._conn = self._create_connection()
        self._init_db()

    def _create_connection(self) -> sqlite3.Connection:
        """Creates and returns a connection configured with WAL mode and a busy timeout."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Initializes tables for tracking rolling daily limits and session states."""
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_usage (
                    usage_date TEXT PRIMARY KEY,
                    task_count INTEGER NOT NULL DEFAULT 0
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    repo_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_json TEXT
                )
            """)
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_repo_status ON sessions(repo_name, status)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")

    def get_today_count(self) -> int:
        """Retrieves task count dispatched for current UTC date."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT task_count FROM daily_usage WHERE usage_date = ?", (today,)
        ).fetchone()
        return row[0] if row else 0

    def increment_daily_usage(self) -> int:
        """Atomically increments and returns the daily dispatch count for UTC today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._conn:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO daily_usage (usage_date, task_count)
                VALUES (?, 1)
                ON CONFLICT(usage_date) DO UPDATE SET task_count = task_count + 1
            """, (today,))

            row = cursor.execute(
                "SELECT task_count FROM daily_usage WHERE usage_date = ?", (today,)
            ).fetchone()
            return row[0] if row else 1

    def record_session(
        self, session_id: str, repo_name: str, status: str = "IN_PROGRESS"
    ) -> None:
        """Records initial session dispatch."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute("""
                INSERT INTO sessions (session_id, repo_name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at
            """, (session_id, repo_name, status, now, now))

    def update_session(
        self,
        session_id: str,
        status: str,
        result_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Updates session status and serializes final execution/result payloads."""
        now = datetime.now(timezone.utc).isoformat()
        raw_json = json.dumps(result_data) if result_data is not None else None
        with self._conn:
            self._conn.execute("""
                UPDATE sessions
                SET status = ?,
                    updated_at = ?,
                    result_json = COALESCE(?, result_json)
                WHERE session_id = ?
            """, (status, now, raw_json, session_id))

    def get_active_sessions(self) -> List[Dict[str, str]]:
        """Returns all non-terminal sessions for crash-recovery polling."""
        cursor = self._conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT session_id, repo_name, status FROM sessions WHERE status IN ('PENDING', 'IN_PROGRESS')"
        )
        return [dict(row) for row in cursor.fetchall()]

    def is_repo_completed(self, repo_name: str) -> bool:
        """Determines if a repository has already undergone a successful audit."""
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE repo_name = ? AND status = 'COMPLETED' LIMIT 1",
            (repo_name,),
        ).fetchone()
        return row is not None
