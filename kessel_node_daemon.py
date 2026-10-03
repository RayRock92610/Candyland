#!/usr/bin/env python3
import time
import signal
import sys
import threading
import sqlite3

class KesselDaemon:
    def __init__(self, db_path="kessel_state.db"):
        self.db_path = db_path
        self.running = True
        self.BUSY_TIMEOUT_MS = 5000

    def _sig_handler(self, sig, frame):
        print(f"\n[*] Received signal {sig}. Gracefully shutting down daemon...")
        self.running = False

    def setup_signals(self):
        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

    def init_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.BUSY_TIMEOUT_MS / 1000.0,
            isolation_level=None,  # Autocommit mode; manage transactions explicitly
            check_same_thread=True  # Ensure single-thread pinning
        )
        # Enable Write-Ahead Logging for high-throughput concurrent reads/writes
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(f"PRAGMA busy_timeout={self.BUSY_TIMEOUT_MS};")
        return conn

    def process_queue(self, conn: sqlite3.Connection) -> int:
        """
        Executes queue polling inside an explicit transaction block.
        Returns the number of processed records.
        """
        conn.execute("BEGIN IMMEDIATE;")
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT task_id, command
                FROM tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 10;
                """
            )
            tasks = cursor.fetchall()

            if not tasks:
                conn.execute("COMMIT;")
                return 0

            for task_id, command in tasks:
                # Process task dispatch
                # For this stub daemon we just mark it as processing
                cursor.execute(
                    "UPDATE tasks SET status = 'processing' WHERE task_id = ?;",
                    (task_id,),
                )

            conn.execute("COMMIT;")
            return len(tasks)

        except Exception:
            conn.execute("ROLLBACK;")
            raise

    def run(self):
        print("[*] Kessel Daemon Starting...")

        try:
            self.setup_signals()
        except ValueError:
            print("[*] Running in a thread, skipping signal handlers.")


        conn = None
        try:
            conn = self.init_connection()
            print("[*] Database connection initialized outside polling loop.")

            while self.running:
                try:
                    processed = self.process_queue(conn)

                    if processed == 0:
                        print("[*] Daemon heartbeat: Node is alive and waiting for consensus tasks.")

                    # Dynamic backoff: poll fast when active, back off when idle
                    sleep_time = 0.05 if processed > 0 else 5.0

                    # Simple sleep to prevent busy-waiting while respecting shutdown
                    slept = 0
                    while slept < sleep_time and self.running:
                        time.sleep(0.1)
                        slept += 0.1

                except sqlite3.OperationalError as e:
                    print(f"[!] Database operational error: {e}. Reconnecting...")
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass
                    time.sleep(1.0)
                    conn = self.init_connection()

                except Exception as e:
                    print(f"[!] Unhandled error in daemon loop: {e}")
                    time.sleep(1.0)

        finally:
            if conn:
                conn.close()
                print("[*] Database connection closed gracefully.")
            print("[*] Kessel Daemon Stopped.")

if __name__ == "__main__":
    KesselDaemon().run()
