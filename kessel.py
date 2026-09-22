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
                    with session.get(url, headers=self.headers, timeout=4, verify=True, allow_redirects=False) as r:
                        if r.status_code == 200 and self.is_truth(r):
                            size = len(r.content)
                            print(f"[!!!] VERIFIED FIND: {url} ({size} bytes)")
                            valid_hits.append((target, p, size))
                except:
                    pass
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

if __name__ == "__main__":
    Kessel("RECON").run_audit()
