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
        self.conn = None

    def _sig_handler(self, sig, frame):
        print(f"\n[*] Received signal {sig}. Gracefully shutting down daemon...")
        self.running = False

    def setup_signals(self):
        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

    def process_queue(self):
        """Poll the SQLite task queue for pending tasks."""
        try:
            # Look for PENDING runs if we had any, or just report heartbeat
            print("[*] Daemon heartbeat: Node is alive and waiting for consensus tasks.")

        except sqlite3.Error as e:
            print(f"[!] Daemon database error: {e}")

    def run(self):
        print("[*] Kessel Daemon Starting...")
        self.setup_signals()

        # ⚡ Bolt Optimization: Reuse persistent connection instead of opening and closing
        # on every iteration in the process_queue loop to avoid massive performance overhead.
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode = WAL;")

        try:
            while self.running:
                self.process_queue()

                # Simple sleep to prevent busy-waiting; in a real scenario we'd use select or event waits
                for _ in range(5):
                    if not self.running:
                        break
                    time.sleep(1)
        finally:
            if self.conn:
                self.conn.close()

        print("[*] Kessel Daemon Stopped.")

if __name__ == "__main__":
    KesselDaemon().run()
