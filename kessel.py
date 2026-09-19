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

        text = response.text
        # If the file is empty or just whitespace
        # ⚡ Bolt Optimization: Replace text.strip() with text.isspace()
        # text.strip() allocates an expensive complete string copy in memory,
        # whereas text.isspace() short-circuits and avoids expensive memory allocation.
        if not text or text.isspace():
            return False

        # ⚡ Bolt Optimization: Avoid lowercasing entire unconstrained payloads.
        # We only need to check the beginning of the file for HTML tags.
        chunk = text[:8192].lower()
        # If it contains HTML tags, it is a webpage, not a config file.
        if "<!doctype html" in chunk or "<html" in chunk or "<body" in chunk:
            return False
        return True

    def audit_node(self, target):
        valid_hits = []
        # ⚡ Bolt Optimization: Use requests.Session() to reuse the underlying TCP connection
        # across multiple requests to the same target, drastically reducing latency.
        with requests.Session() as session:
            for p in self.paths:
                url = f"https://{target}{p}"
                try:
                    # ⚡ Bolt Optimization: Removed stream=True. By allowing requests to fully download
                    # the response body automatically, the connection is safely returned to the urllib3
                    # connection pool. This avoids dropping connections on short-circuits and saves significant
                    # latency by reusing TLS sessions across multiple requests to the same target.
                    with session.get(url, headers=self.headers, timeout=4, verify=True, allow_redirects=False) as r:
                        if r.status_code == 200 and self.is_truth(r):
                            size = len(r.content)
                            print(f"[!!!] VERIFIED FIND: {url} ({size} bytes)")
                            valid_hits.append((target, p, size))
                except:
                    pass
        return valid_hits

    def run_audit(self):
        with sqlite3.connect(self.db_path) as conn:
            # Only audit targets that were previously found to be 'Live'
            targets = [row[0] for row in conn.execute("SELECT target FROM recon WHERE status_code=200")]
        
        if not targets:
            print("[!] No 200-OK targets in DB. Run a probe first.")
            return

        print(f"[*] KESSEL::AUDIT -> Validating {len(targets)} targets against the Truth Gate...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(self.audit_node, targets)
        print("[*] Audit Complete.")

if __name__ == "__main__":
    Kessel("RECON").run_audit()
