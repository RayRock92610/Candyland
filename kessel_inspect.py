#!/usr/bin/env python3
import os
import json
import sqlite3

class KesselInspector:
    def __init__(self, db_path="kessel_state.db"):
        self.db_path = db_path

    def inspect_config(self):
        print("[*] Inspecting configurations...")
        if not os.path.exists("config.example.json"):
            print("[!] config.example.json is missing.")
        else:
            try:
                with open("config.example.json") as f:
                    json.load(f)
                print("[+] config.example.json is valid.")
            except json.JSONDecodeError:
                print("[!] config.example.json has invalid JSON syntax.")

    def inspect_state(self):
        print("[*] Inspecting local state database...")
        if not os.path.exists(self.db_path):
            print(f"[!] Database {self.db_path} not found.")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            # Verify WAL mode
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            print(f"[*] DB Journal Mode: {mode}")

            # Check tables
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            expected = ["tasks", "agent_runs", "audit_events"]
            for ext in expected:
                if ext in tables:
                    count = conn.execute(f"SELECT count(*) FROM {ext}").fetchone()[0]
                    print(f"[+] Table '{ext}' found ({count} rows).")
                else:
                    print(f"[!] Table '{ext}' is missing.")

            # Check Active Tasks
            if "tasks" in tables:
                active = conn.execute("SELECT task_id, status FROM tasks WHERE status NOT IN ('COMPLETED', 'FAILED', 'ERROR')").fetchall()
                if active:
                    print(f"[*] Found {len(active)} active tasks.")
                    for t in active:
                        print(f"  - {t[0]}: {t[1]}")
                else:
                    print("[+] No active/stuck tasks.")

        except sqlite3.Error as e:
            print(f"[!] SQLite Error during inspection: {e}")
        finally:
            conn.close()

    def run(self):
        self.inspect_config()
        print("")
        self.inspect_state()

if __name__ == "__main__":
    KesselInspector().run()
