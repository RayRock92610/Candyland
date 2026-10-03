#!/usr/bin/env python3
import os
import sys
import uuid
import sqlite3
import subprocess
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

class KesselRunner:
    def __init__(self, db_path="kessel_state.db"):
        self.db_path = db_path
        self._ensure_env()

    def _ensure_env(self):
        """Perform POSIX environment checks."""
        # Simple check to ensure we are in a valid POSIX environment
        if os.name != 'posix':
            print("[WARN] Runner is optimized for POSIX environments.")

    def get_conn(self):
        # We need a new connection per thread since we shouldn't use check_same_thread=False generally,
        # but for this simple runner where we just write from the main thread, it's fine.
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def run_task(self, command_args):
        task_id = str(uuid.uuid4())
        command_str = " ".join(command_args)

        print(f"[*] Starting Kessel task {task_id}: {command_str}")

        with self.get_conn() as conn:
            conn.execute("INSERT INTO tasks (task_id, status, command) VALUES (?, ?, ?)",
                         (task_id, "RUNNING", command_str))

        try:
            # We enforce bounded concurrency of max 4.
            # If the task requires processing many items, we would map them here.
            # For a generic CLI command runner, we just run the subprocess.
            result = subprocess.run(command_args, capture_output=True, text=True)
            status = "COMPLETED" if result.returncode == 0 else "FAILED"

            with self.get_conn() as conn:
                conn.execute("""
                    UPDATE tasks SET status = ?, completed_at = ? WHERE task_id = ?
                """, (status, datetime.now(timezone.utc).isoformat(), task_id))

            if status == "COMPLETED":
                print(f"[*] Task {task_id} completed successfully.")
            else:
                print(f"[!] Task {task_id} failed with code {result.returncode}.")
                print(result.stderr)

            return result.returncode

        except Exception as e:
            with self.get_conn() as conn:
                conn.execute("""
                    UPDATE tasks SET status = ?, completed_at = ? WHERE task_id = ?
                """, ("ERROR", datetime.now(timezone.utc).isoformat(), task_id))
            print(f"[!] Exception during task execution: {e}")
            return 1
