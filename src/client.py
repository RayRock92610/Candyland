"""
src/client.py - HTTP transport, rate limiting, and session client for the Jules API.
"""

import asyncio
import json
import logging
import random
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("jules_client")


class JulesRateLimiter:
    """Manages active task concurrency and exponential backoff with jitter."""

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
        # Full jitter exponential backoff: uniform(0.5, 1.0) * min(max_backoff, base * 2^attempt)
        delay = min(self.max_backoff, self.base_backoff * (2 ** attempt))
        return random.uniform(0.5, 1.0) * delay


class JulesClient:
    """Client wrapper for Google Jules API (v1alpha)."""

    def __init__(
        self,
        api_key: str,
        limiter: Optional[JulesRateLimiter] = None,
        base_url: str = "https://jules.googleapis.com/v1alpha",
    ):
        if not api_key:
            raise ValueError("Jules API key must be provided.")
        self.api_key = api_key
        self.limiter = limiter or JulesRateLimiter()
        self.base_url = base_url.rstrip("/")
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
        """Executes an HTTP request with exponential backoff on 429/5xx errors."""
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
                    logger.warning(
                        "Rate limit (429) hit on %s. Backoff: %.2fs (attempt %d/%d)",
                        endpoint,
                        delay,
                        attempt + 1,
                        self.limiter.max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in (500, 502, 503, 504):
                    delay = self.limiter.calculate_backoff(attempt)
                    logger.warning(
                        "Server error (%d) on %s. Retrying in %.2fs...",
                        response.status_code,
                        endpoint,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Permanent client failure (400, 401, 403, 404)
                # ⚡ Bolt Optimization: Slicing response.content directly before decoding avoids the massive performance overhead of full-payload decoding via response.text when dealing with large payloads on terminal errors.
                logger.error(
                    "Permanent error %d on %s: %s",
                    response.status_code,
                    endpoint,
                    response.content[:8192].decode('utf-8', errors='replace'),
                )
                return None

            except httpx.RequestError as exc:
                delay = self.limiter.calculate_backoff(attempt)
                logger.error(
                    "Network error on %s: %s. Retrying in %.2fs...",
                    endpoint,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        logger.critical("Max retries exceeded for %s", endpoint)
        return None

    async def create_session(
        self,
        client: httpx.AsyncClient,
        repo_name: str,
        audit_prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Initializes a new analysis session guarded by the concurrency semaphore."""
        payload = {
            "prompt": audit_prompt,
            "sourceContext": {
                "source": f"sources/github/{repo_name}",
                "githubRepoContext": {
                    "startingBranch": "main",
                },
            },
            "automationMode": "AUTO_CREATE_PR",
            "title": f"Workflow Audit: {repo_name}",
        }

        async with self.limiter.semaphore:
            logger.info("Semaphore slot acquired. Dispatching session for: %s", repo_name)
            return await self.request_with_retry(
                client=client,
                method="POST",
                endpoint="sessions",
                json_data=payload,
            )
