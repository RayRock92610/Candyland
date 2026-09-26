"""
src/orchestrator.py - Core dispatch and lifecycle management for Jules audit sessions.
"""

import asyncio
import logging
from typing import Any, Optional

import httpx

from src.client import JulesClient
from src.state_store import StateStore

logger = logging.getLogger("jules_orchestrator")


class JulesOrchestrator:
    def __init__(
        self,
        client: JulesClient,
        store: StateStore,
        max_daily_quota: int = 15,
        poll_interval_secs: float = 15.0,
    ):
        self.client = client
        self.store = store
        self.max_daily_quota = max_daily_quota
        self.poll_interval = poll_interval_secs

    async def poll_session(self, http_client: httpx.AsyncClient, session_id: str) -> str:
        """Polls Jules session status until reaching a terminal state."""
        while True:
            clean_session_id = session_id.removeprefix("sessions/")
            resp = await self.client.request_with_retry(
                http_client, "GET", f"sessions/{clean_session_id}"
            )
            if not resp:
                logger.error("Failed to query status for session: %s", session_id)
                self.store.update_session(session_id, "FAILED")
                return "FAILED"

            state = resp.get("state", resp.get("status", "UNKNOWN")).upper()
            logger.info("Session %s state: %s", session_id, state)

            if state in ("COMPLETED", "SUCCEEDED"):
                self.store.update_session(session_id, "COMPLETED", result_data=resp)
                return "COMPLETED"
            if state in ("FAILED", "CANCELLED", "ERROR"):
                self.store.update_session(session_id, "FAILED", result_data=resp)
                return "FAILED"

            await asyncio.sleep(self.poll_interval)

    async def resume_in_flight(self, http_client: httpx.AsyncClient) -> None:
        """Discovers uncompleted sessions across script restarts and polls them to finish."""
        active = self.store.get_active_sessions()
        if not active:
            return

        logger.info("Resuming %d in-flight session(s) from previous run...", len(active))
        tasks = [self.poll_session(http_client, item["session_id"]) for item in active]
        await asyncio.gather(*tasks)

    async def dispatch_repo(
        self, http_client: httpx.AsyncClient, repo_name: str, prompt: str
    ) -> bool:
        """Checks constraints, dispatches audit request, records state, and attaches poller."""
        if self.store.is_repo_completed(repo_name):
            logger.info("Repository %s already successfully audited. Skipping.", repo_name)
            return True

        current_used = self.store.get_today_count()
        if current_used >= self.max_daily_quota:
            logger.warning(
                "Daily quota reached (%d/%d). Halting dispatch for %s.",
                current_used,
                self.max_daily_quota,
                repo_name,
            )
            return False

        # Concurrency semaphore is enforced inside JulesClient
        session_resp = await self.client.create_session(http_client, repo_name, prompt)
        if not session_resp:
            logger.error("Failed to initialize session for %s", repo_name)
            return False

        session_id = session_resp.get("name", session_resp.get("id"))
        if not session_id:
            logger.error("Invalid response payload (missing session ID): %s", session_resp)
            return False

        # Atomic local tracking
        self.store.increment_daily_usage()
        self.store.record_session(session_id, repo_name, status="IN_PROGRESS")
        logger.info("Session %s created and tracked for %s.", session_id, repo_name)

        # Non-blocking poll attachment
        asyncio.create_task(self.poll_session(http_client, session_id))
        return True
