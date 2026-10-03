#!/usr/bin/env python3
import sqlite3, json, requests, os, sys, http.cookiejar
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


class BlockAllCookies(http.cookiejar.DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False
    def return_ok(self, cookie, request):
        return False


class Kessel:
    def __init__(self, project="RECON"):
        self.db_path = Path(f"kessel_{project}.db")
        self.headers = {"User-Agent": "Mozilla/5.0 (KesselEngine/2.0)"}
        # The paths we are auditing
        self.paths = ["/.git/config", "/.env", "/robots.txt", "/.vscode/settings.json"]

    def is_truth(self, response):
        """The Truth Gate: Filters out Soft 404s and HTML redirects."""
        # ⚡ Bolt Optimization: Fast path using Content-Type headers before reading the body content.
        # This prevents downloading and decoding large HTML payloads.
        if hasattr(response, 'headers'):
            content_type = response.headers.get("Content-Type", "")
            if isinstance(content_type, str) and "text/html" in content_type.lower():
                return False

        # ⚡ Bolt Optimization: Avoid expensive .text decoding for the full payload
        # response.text forces decoding the entire byte payload into a Unicode string.
        # We can check for whitespace and extract just the prefix directly from response.content
        # and decode ONLY what we need.

        content = response.content
        if not content or content.isspace():
            return False

        # ⚡ Bolt Optimization: Avoid lowercasing entire unconstrained payloads.
        # We only need to check the beginning of the file for HTML tags.
        # Calling .lower() on raw bytes and checking byte literals is significantly faster
        # than decoding byte chunks into UTF-8 strings.
        chunk = content[:8192].lower()
        # If it contains HTML tags, it is a webpage, not a config file.
        if b"<!doctype html" in chunk or b"<html" in chunk or b"<body" in chunk:
            return False
        return True

    def audit_node(self, target, session=None):
        valid_hits = []

        local_session = False
        if session is None:
            session = requests.Session()
            local_session = True

        try:
            for p in self.paths:
                url = f"https://{target}{p}"
                try:
                    with session.get(
                        url,
                        headers=self.headers,
                        timeout=(3.0, 5.0),  # (connect_timeout, read_timeout)
                        verify=True,
                        allow_redirects=False
                    ) as r:
                        if r.status_code == 200 and self.is_truth(r):
                            size = len(r.content)
                            print(f"[!!!] VERIFIED FIND: {url} ({size} bytes)")
                            valid_hits.append((target, p, size))
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    # Host is unreachable or connection timed out: break early to save time
                    break
                except requests.exceptions.RequestException:
                    # Specific path failed or timed out reading response: continue to next path
                    continue
                except Exception:
                    continue
        finally:
            if local_session:
                session.close()

        return valid_hits

    def run_audit(self):
        with sqlite3.connect(self.db_path) as conn:
            # ⚡ Bolt Optimization: Add index to status_code column.
            # This turns an O(N) full table scan into an O(log N) index lookup, drastically improving query times for large target databases.
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recon_status_code ON recon(status_code)")

            # Only audit targets that were previously found to be 'Live'
            targets = [row[0] for row in conn.execute("SELECT target FROM recon WHERE status_code=200")]
        
        if not targets:
            print("[!] No 200-OK targets in DB. Run a probe first.")
            return

        print(f"[*] KESSEL::AUDIT -> Validating {len(targets)} targets against the Truth Gate...")
        # ⚡ Bolt Optimization: Reusing a single globally shared requests.Session() across workers is
        # significantly faster than instantiating a new Session object per target.
        # We must disable cookie persistence to prevent cross-target state leakage, and increase
        # the connection pool size to prevent thrashing when hitting many different hosts.
        with requests.Session() as shared_session:
            shared_session.cookies.set_policy(BlockAllCookies())
            adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
            shared_session.mount("https://", adapter)
            shared_session.mount("http://", adapter)

            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(lambda t: self.audit_node(t, session=shared_session), targets)
        print("[*] Audit Complete.")



# ==============================================================================
# Unified CLI Dispatcher logic integrated at the bottom of the existing file
# to preserve the Kessel class used by the tests.
# ==============================================================================
import argparse
import subprocess
from kessel_runner import KesselRunner
from kessel_inspect import KesselInspector
from kessel_node_daemon import KesselDaemon
from kessel_ast_auditor import run_auditor

def handle_init(args):
    print("[*] Initializing Kessel State Tables...")
    result = subprocess.run(["./init_kessel_tables.sh"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    sys.exit(result.returncode)

def handle_run(args):
    if not args.command:
        print("[!] Error: 'run' requires a command to execute.")
        sys.exit(1)
    runner = KesselRunner()
    sys.exit(runner.run_task(args.command))

def handle_status(args):
    print("[*] Querying kessel_state.db for task status...")
    db_path = "kessel_state.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, status, command, created_at, completed_at FROM tasks ORDER BY created_at DESC LIMIT 10")
        rows = cursor.fetchall()

        if not rows:
            print("[+] No tasks found in state database.")
            return

        print(f"{'TASK ID':<40} | {'STATUS':<15} | {'COMMAND':<30} | {'CREATED'}")
        print("-" * 110)
        for row in rows:
            task_id, status, cmd, created, _ = row
            cmd_trunc = cmd[:27] + "..." if len(cmd) > 30 else cmd
            print(f"{task_id:<40} | {status:<15} | {cmd_trunc:<30} | {created}")

    except sqlite3.Error as e:
        print(f"[!] Database error querying status: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

def handle_triage(args):
    print("[*] Triaging unhandled exceptions and security gate events...")
    db_path = "kessel_state.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("\n--- Failed Tasks ---")
        cursor.execute("SELECT task_id, status, command FROM tasks WHERE status IN ('FAILED', 'ERROR')")
        failed = cursor.fetchall()
        if failed:
            for f in failed:
                print(f"  - {f[0]} [{f[1]}]: {f[2]}")
        else:
            print("  None.")

        print("\n--- Audit Events ---")
        cursor.execute("SELECT event_type, severity, file_path, description FROM audit_events ORDER BY created_at DESC LIMIT 10")
        events = cursor.fetchall()
        if events:
            for e in events:
                print(f"  - [{e[1]}] {e[0]} in {e[2]}: {e[3]}")
        else:
            print("  None.")

    except sqlite3.Error as e:
        print(f"[!] Database error querying triage info: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

def handle_audit(args):
    if not args.path:
        print("[!] Error: 'audit' requires a path to inspect.")
        sys.exit(1)
    sys.exit(run_auditor(args.path))

def handle_daemon(args):
    daemon = KesselDaemon()
    daemon.run()

def handle_inspect(args):
    inspector = KesselInspector()
    inspector.run()

def main():
    parser = argparse.ArgumentParser(description="Kessel Flow - Unified CLI Dispatcher")
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand")

    # Subcommand: init
    parser_init = subparsers.add_parser("init", help="Initialize local SQLite state tables")
    parser_init.set_defaults(func=handle_init)

    # Subcommand: run
    parser_run = subparsers.add_parser("run", help="Executes pipeline stages with bounded concurrency")
    parser_run.add_argument("command", nargs=argparse.REMAINDER, help="Command to run via kessel runner")
    parser_run.set_defaults(func=handle_run)

    # Subcommand: status
    parser_status = subparsers.add_parser("status", help="Queries active runs, agent health, and exit states")
    parser_status.set_defaults(func=handle_status)

    # Subcommand: triage
    parser_triage = subparsers.add_parser("triage", help="Surfaces recent unhandled exceptions and security gate events")
    parser_triage.set_defaults(func=handle_triage)

    # Subcommand: audit
    parser_audit = subparsers.add_parser("audit", help="Runs AST static analysis with hardened enforcement")
    parser_audit.add_argument("path", help="File or directory to audit")
    parser_audit.set_defaults(func=handle_audit)

    # Subcommand: daemon
    parser_daemon = subparsers.add_parser("daemon", help="Starts the background node daemon loop")
    parser_daemon.set_defaults(func=handle_daemon)

    # Subcommand: inspect
    parser_inspect = subparsers.add_parser("inspect", help="Diagnostic CLI inspection tool")
    parser_inspect.set_defaults(func=handle_inspect)

    args = parser.parse_args()

    if args.subcommand is None:
        # Default behavior: run original script
        Kessel("RECON").run_audit()
        sys.exit(0)

    # Dispatch
    args.func(args)

if __name__ == "__main__":
    main()
