#!/usr/bin/env python3
import sqlite3, json, requests, os, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


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
        chunk = content[:8192].decode('utf-8', errors='ignore').lower()
        # If it contains HTML tags, it is a webpage, not a config file.
        if "<!doctype html" in chunk or "<html" in chunk or "<body" in chunk:
            return False
        return True

    def audit_node(self, target):
        valid_hits = []
        # ⚡ Bolt Optimization: Use a shared requests.Session() to eliminate session instantiation overhead per target.
        for p in self.paths:
            url = f"https://{target}{p}"
            try:
                # ⚡ Bolt Optimization: Removed stream=True. By allowing requests to fully download
                # the response body automatically, the connection is safely returned to the urllib3
                # connection pool. This avoids dropping connections on short-circuits and saves significant
                # latency by reusing TLS sessions across multiple requests to the same target.
                with self.session.get(url, headers=self.headers, timeout=4, verify=True, allow_redirects=False) as r:
                    if r.status_code == 200 and self.is_truth(r):
                        size = len(r.content)
                        print(f"[!!!] VERIFIED FIND: {url} ({size} bytes)")
                        valid_hits.append((target, p, size))
            except:
                pass
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
        with requests.Session() as session:
            self.session = session
            with ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(self.audit_node, targets)
        print("[*] Audit Complete.")

if __name__ == "__main__":
    Kessel("RECON").run_audit()
