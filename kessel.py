#!/usr/bin/env python3
import sqlite3, json, requests, os, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

class Kessel:
    def __init__(self, project="RECON"):
        self.db_path = Path(f"kessel_{project}.db")
        self.headers = {"User-Agent": "Mozilla/5.0 (KesselEngine/2.0)"}
        # The paths we are auditing
        self.paths = ["/.git/config", "/.env", "/robots.txt", "/.vscode/settings.json"]

    def is_truth(self, response):
        """The Truth Gate: Filters out Soft 404s and HTML redirects."""
        content = response.text.lower()
        # If it contains HTML tags, it is a webpage, not a config file.
        if "<!doctype html" in content or "<html" in content or "<body" in content:
            return False
        # If the file is empty or just whitespace
        if not content.strip():
            return False
        return True

    def audit_node(self, target):
        valid_hits = []
        for p in self.paths:
            url = f"https://{target}{p}"
            try:
                # Use allow_redirects=False to catch the redirect attempt
                r = requests.get(url, headers=self.headers, timeout=4, verify=False, allow_redirects=False)
                
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
