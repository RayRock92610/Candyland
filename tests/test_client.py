"""
tests/test_client.py - Unit tests for JulesClient error backoff, retry ceilings, and auth traps.
"""

from unittest.mock import AsyncMock, patch
import httpx
import pytest

from src.client import JulesClient, JulesRateLimiter


@pytest.fixture
def client_fast_backoff():
    limiter = JulesRateLimiter(
        max_concurrent_tasks=2,
        base_backoff_secs=0.001,
        max_backoff_secs=0.01,
        max_retries=3,
    )
    return JulesClient(api_key="valid-test-key", limiter=limiter)


@pytest.mark.asyncio
async def test_request_with_retry_429_success(client_fast_backoff):
    """Ensures 429 triggers backoff and subsequent 200 returns data."""
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    resp_429 = httpx.Response(429, headers={"Retry-After": "0.001"})
    resp_200 = httpx.Response(200, json={"status": "ok"})

    mock_http.request.side_effect = [resp_429, resp_200]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await client_fast_backoff.request_with_retry(mock_http, "GET", "sessions/1")

    assert res == {"status": "ok"}
    assert mock_http.request.call_count == 2
    mock_sleep.assert_called_once_with(0.001)


@pytest.mark.asyncio
async def test_request_with_retry_unrecoverable_auth_error(client_fast_backoff):
    """Ensures 401/403 fails immediately without exhausting retries."""
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    resp_403 = httpx.Response(403, text="Forbidden: Invalid credentials")
    mock_http.request.return_value = resp_403

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await client_fast_backoff.request_with_retry(mock_http, "POST", "sessions")

    assert res is None
    # Must fail fast on attempt 1
    assert mock_http.request.call_count == 1
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_request_with_retry_max_retries_exceeded(client_fast_backoff):
    """Ensures recurring 503 errors back off up to max_retries then return None."""
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    resp_503 = httpx.Response(503, text="Service Unavailable")
    mock_http.request.return_value = resp_503

    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await client_fast_backoff.request_with_retry(mock_http, "GET", "sessions/1")

    assert res is None
    assert mock_http.request.call_count == 3  # Matches max_retries in fixture
