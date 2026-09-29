#!/usr/bin/env python3
"""
jules_dispatcher.py - Automated repository audit orchestrator for the Jules API.
Production-ready: incorporates SQLite state tracking, rate limiting, and filtering.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import random
import sqlite3
import sys
import threading
from typing import Any, Dict, List, Optional, Set

import httpx

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("jules_orchestrator")


# ---------------------------------------------------------------------------
# Database & State Store
# ---------------------------------------------------------------------------
class StateStore:
    def __init__(self, db_path: str = "jules_audit.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            # ⚡ Bolt Optimization: Reuse a persistent thread-local connection with WAL mode
            # to avoid the overhead of reopening the connection on every method call while ensuring thread safety.
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
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
            # ⚡ Bolt Optimization: Add indices for frequently queried columns
            # to turn O(N) full table scans into O(log N) index lookups.
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_repo_status ON sessions(repo_name, status)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")

    def get_today_count(self) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT task_count FROM daily_usage WHERE usage_date = ?", (today,)
        ).fetchone()
        return row[0] if row else 0

    def increment_daily_usage(self) -> int:
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

    def record_session(self, session_id: str, repo_name: str, status: str = "IN_PROGRESS"):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute("""
                INSERT INTO sessions (session_id, repo_name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at
            """, (session_id, repo_name, status, now, now))

    def update_session(self, session_id: str, status: str, result_data: Optional[Dict[str, Any]] = None):
        now = datetime.now(timezone.utc).isoformat()
        raw_json = json.dumps(result_data) if result_data else None
        with self._conn:
            self._conn.execute("""
                UPDATE sessions
                SET status = ?, updated_at = ?, result_json = COALESCE(?, result_json)
                WHERE session_id = ?
            """, (status, now, raw_json, session_id))

    def get_active_sessions(self) -> List[Dict[str, str]]:
        # ⚡ Bolt Optimization: Use a local cursor for sqlite3.Row instead of modifying global _conn.row_factory
        # This prevents global state mutation which causes side effects when the connection is reused.
        cursor = self._conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            "SELECT session_id, repo_name, status FROM sessions WHERE status IN ('PENDING', 'IN_PROGRESS')"
        )
        return [dict(row) for row in cursor.fetchall()]

    def is_repo_completed(self, repo_name: str) -> bool:
        # ⚡ Bolt Optimization: Use LIMIT 1 to short-circuit the scan once a match is found
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE repo_name = ? AND status = 'COMPLETED' LIMIT 1", (repo_name,)
        ).fetchone()
        return row is not None


# ---------------------------------------------------------------------------
# Rate Limiter & Concurrency Throttle
# ---------------------------------------------------------------------------
class JulesRateLimiter:
    def __init__(
        self,
        max_concurrent_tasks: int = 3,
        base_backoff_secs: float = 2.0,
        max_backoff_secs: float = 60.0,
        max_retries: int = 5,
    ):
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.base_backoff = base_backoff_secs
        self.max_backoff = max_backoff_secs
        self.max_retries = max_retries

    def calculate_backoff(self, attempt: int, retry_after: Optional[str] = None) -> float:
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        delay = min(self.max_backoff, self.base_backoff * (2 ** attempt))
        return random.uniform(0.5, 1.0) * delay


# ---------------------------------------------------------------------------
# Jules API Client
# ---------------------------------------------------------------------------
class JulesClient:
    def __init__(self, api_key: str, limiter: JulesRateLimiter):
        self.api_key = api_key
        self.limiter = limiter
        self.base_url = "https://jules.googleapis.com/v1alpha"
        self.headers = {
            "X-Goog-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        for attempt in range(self.limiter.max_retries):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_data,
                    timeout=30.0,
                )

                if response.status_code in (200, 201):
                    return json.loads(response.content)

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = self.limiter.calculate_backoff(attempt, retry_after)
                    logger.warning("HTTP 429 encountered on %s. Backoff: %.2fs (attempt %d)", endpoint, delay, attempt + 1)
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in (500, 502, 503, 504):
                    delay = self.limiter.calculate_backoff(attempt)
                    logger.warning("Server error %d on %s. Retry in %.2fs", response.status_code, endpoint, delay)
                    await asyncio.sleep(delay)
                    continue

                # Use response.content with truncation to avoid full payload decoding on error
                error_body = response.content[:8192].decode('utf-8', errors='replace')
                logger.error("Terminal failure %d on %s: %s", response.status_code, endpoint, error_body)
                return None

            except httpx.RequestError as exc:
                delay = self.limiter.calculate_backoff(attempt)
                logger.error("Network error %s on %s. Retry in %.2fs", exc, endpoint, delay)
                await asyncio.sleep(delay)

        logger.critical("Max retries exceeded for endpoint: %s", endpoint)
        return None

    async def create_session(
        self, client: httpx.AsyncClient, repo_name: str, audit_prompt: str
    ) -> Optional[Dict[str, Any]]:

        # Apply DevOps & Repository Code Health Tracker directive
        health_tracker_directive = "\n\nIMPORTANT: For DevOps & Repository Code Health Tracker audits and digest configurations, focus exclusively on functional, actionable remediation items and suppress minor cosmetic and formatting notices."
        enhanced_prompt = audit_prompt + health_tracker_directive

        payload = {
            "prompt": enhanced_prompt,
            "sourceContext": {
                "gitHub": {
                    "repository": repo_name,
                }
            },
        }
        return await self.request_with_retry(
            client=client,
            method="POST",
            endpoint="sessions",
            json_data=payload,
        )


# ---------------------------------------------------------------------------
# GitHub Repository Discovery & Filter Engine
# ---------------------------------------------------------------------------
class RepoFilterEngine:
    def __init__(
        self,
        github_token: Optional[str] = None,
        target_languages: Optional[Set[str]] = None,
        excluded_repos: Optional[Set[str]] = None,
    ):
        self.token = github_token
        self.target_languages = {l.lower() for l in target_languages} if target_languages else set()
        self.excluded_repos = {r.lower() for r in excluded_repos} if excluded_repos else set()
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    async def fetch_user_repos(self, client: httpx.AsyncClient, owner: str) -> List[Dict[str, Any]]:
        repos = []
        page = 1
        while True:
            url = f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}"
            resp = await client.get(url, headers=self.headers, timeout=20.0)
            if resp.status_code != 200:
                # Use response.content with truncation to avoid full payload decoding on error
                error_body = resp.content[:8192].decode('utf-8', errors='replace')
                logger.error("Failed fetching repos for %s: %s", owner, error_body)
                break
            batch = json.loads(resp.content)
            if not batch:
                break
            repos.extend(batch)
            page += 1
        return repos

    def evaluate(self, repo: Dict[str, Any]) -> bool:
        full_name = repo.get("full_name", "").lower()
        is_archived = repo.get("archived", False)
        is_fork = repo.get("fork", False)
        primary_lang = (repo.get("language") or "").lower()

        if is_archived:
            return False
        if full_name in self.excluded_repos:
            return False
        if self.target_languages and primary_lang not in self.target_languages:
            return False

        return True


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------
class DispatchPipeline:
    def __init__(
        self,
        client: JulesClient,
        store: StateStore,
        filter_engine: RepoFilterEngine,
        daily_limit: int,
    ):
        self.client = client
        self.store = store
        self.filter = filter_engine
        self.daily_limit = daily_limit

    async def poll_session(self, http_client: httpx.AsyncClient, session_id: str):
        interval = 15.0
        while True:
            resp = await self.client.request_with_retry(http_client, "GET", f"sessions/{session_id}")
            if not resp:
                self.store.update_session(session_id, "FAILED")
                return

            state = resp.get("state", resp.get("status", "UNKNOWN"))
            logger.info("Session %s status: %s", session_id, state)

            if state in ("COMPLETED", "SUCCEEDED"):
                self.store.update_session(session_id, "COMPLETED", result_data=resp)
                return
            elif state in ("FAILED", "CANCELLED", "ERROR"):
                self.store.update_session(session_id, "FAILED", result_data=resp)
                return

            await asyncio.sleep(interval)

    async def resume_in_flight(self, http_client: httpx.AsyncClient):
        active = self.store.get_active_sessions()
        if not active:
            return
        logger.info("Found %d pending session(s). Polling to completion...", len(active))
        tasks = [self.poll_session(http_client, item["session_id"]) for item in active]
        await asyncio.gather(*tasks)

    async def process_repo(
        self, http_client: httpx.AsyncClient, repo_name: str, prompt: str
    ) -> bool:
        if self.store.is_repo_completed(repo_name):
            logger.info("Skipping %s: audit previously completed.", repo_name)
            return True

        if self.store.get_today_count() >= self.daily_limit:
            logger.warning("Daily task limit reached (%d/%d).", self.store.get_today_count(), self.daily_limit)
            return False

        async with self.client.limiter.semaphore:
            # Double-check daily budget inside lock boundary
            if self.store.get_today_count() >= self.daily_limit:
                return False

            logger.info("Starting dispatch for %s", repo_name)
            session = await self.client.create_session(http_client, repo_name, prompt)
            if not session:
                logger.error("Failed to create audit session for %s", repo_name)
                return False

            session_id = session.get("name", session.get("id"))
            if not session_id:
                logger.error("API response lacked valid session ID: %s", session)
                return False

            self.store.increment_daily_usage()
            self.store.record_session(session_id, repo_name, status="IN_PROGRESS")
            logger.info("Session initialized: %s -> ID: %s", repo_name, session_id)

            await self.poll_session(http_client, session_id)
            return True


# ---------------------------------------------------------------------------
# Main Execution Entry Point
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Jules API Workflow Improvement Dispatcher")
    parser.add_argument("--owner", required=True, help="GitHub user or organization name")
    parser.add_argument("--prompt", required=True, help="Workflow improvement audit prompt")
    parser.add_argument("--languages", nargs="*", default=[], help="Allowed languages (e.g. Python Go Bash)")
    parser.add_argument("--exclude", nargs="*", default=[], help="Full repository names to exclude")
    parser.add_argument("--daily-limit", type=int, default=15, help="Maximum allowed task executions per 24 hours")
    parser.add_argument("--max-concurrent", type=int, default=3, help="Max parallel running sessions")
    parser.add_argument("--db-path", default="jules_audit.db", help="SQLite database path")
    args = parser.parse_args()

    jules_api_key = os.environ.get("JULES_API_KEY")
    if not jules_api_key:
        logger.critical("JULES_API_KEY environment variable is not set. Terminating.")
        sys.exit(1)

    github_token = os.environ.get("GITHUB_TOKEN")

    limiter = JulesRateLimiter(max_concurrent_tasks=args.max_concurrent)
    client = JulesClient(api_key=jules_api_key, limiter=limiter)
    store = StateStore(db_path=args.db_path)
    filter_engine = RepoFilterEngine(
        github_token=github_token,
        target_languages=set(args.languages),
        excluded_repos=set(args.exclude),
    )
    pipeline = DispatchPipeline(client, store, filter_engine, daily_limit=args.daily_limit)

    async with httpx.AsyncClient() as http_client:
        # Step 1: Resume unfinished work
        await pipeline.resume_in_flight(http_client)

        # Step 2: Fetch and filter repository targets
        logger.info("Scanning repositories for owner: %s", args.owner)
        all_repos = await filter_engine.fetch_user_repos(http_client, args.owner)
        target_repos = [r["full_name"] for r in all_repos if filter_engine.evaluate(r)]
        logger.info("Discovered %d candidate repos meeting criteria.", len(target_repos))

        # Step 3: Dispatch sequentially across available concurrency slots
        for repo_name in target_repos:
            success = await pipeline.process_repo(http_client, repo_name, args.prompt)
            if not success and pipeline.store.get_today_count() >= pipeline.daily_limit:
                logger.warning("Halting batch: daily cap reached.")
                break

    logger.info("Dispatch operations completed.")

if __name__ == "__main__":
    asyncio.run(main())
