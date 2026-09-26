"""
tests/test_orchestrator.py - Unit test suite for JulesOrchestrator lifecycle and state handling.
"""

from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

from src.client import JulesClient, JulesRateLimiter
from src.orchestrator import JulesOrchestrator
from src.state_store import StateStore


@pytest.fixture
def temp_db(tmp_path):
    """Provides an isolated SQLite database path per test."""
    db_file = tmp_path / "test_jules.db"
    return str(db_file)


@pytest.fixture
def state_store(temp_db):
    return StateStore(db_path=temp_db)


@pytest.fixture
def mock_client():
    limiter = JulesRateLimiter(max_concurrent_tasks=2, base_backoff_secs=0.01)
    client = JulesClient(api_key="test-api-key", limiter=limiter)
    client.create_session = AsyncMock()
    client.request_with_retry = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_dispatch_repo_quota_exhausted(state_store, mock_client):
    """Ensures dispatch halts immediately when daily quota is reached."""
    # Pre-fill usage to quota limit
    state_store.increment_daily_usage()
    state_store.increment_daily_usage()

    orchestrator = JulesOrchestrator(
        client=mock_client,
        store=state_store,
        max_daily_quota=2,
        poll_interval_secs=0.01,
    )

    async with httpx.AsyncClient() as http_client:
        result = await orchestrator.dispatch_repo(
            http_client=http_client,
            repo_name="org/test-repo",
            prompt="Audit repo",
        )

    assert result is False
    mock_client.create_session.assert_not_called()
    assert state_store.get_today_count() == 2


@pytest.mark.asyncio
async def test_dispatch_repo_skips_completed(state_store, mock_client):
    """Ensures repositories marked COMPLETED in the database are bypassed."""
    state_store.record_session("session-123", "org/audited-repo", status="COMPLETED")

    orchestrator = JulesOrchestrator(
        client=mock_client,
        store=state_store,
        max_daily_quota=10,
        poll_interval_secs=0.01,
    )

    async with httpx.AsyncClient() as http_client:
        result = await orchestrator.dispatch_repo(
            http_client=http_client,
            repo_name="org/audited-repo",
            prompt="Audit repo",
        )

    assert result is True
    mock_client.create_session.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_repo_success(state_store, mock_client):
    """Ensures valid dispatch increments daily quota and records session."""
    mock_client.create_session.return_value = {"name": "sessions/sess-999"}
    # Mock polling status response
    mock_client.request_with_retry.return_value = {"state": "COMPLETED"}

    orchestrator = JulesOrchestrator(
        client=mock_client,
        store=state_store,
        max_daily_quota=10,
        poll_interval_secs=0.01,
    )

    async with httpx.AsyncClient() as http_client:
        result = await orchestrator.dispatch_repo(
            http_client=http_client,
            repo_name="org/target-repo",
            prompt="Audit repo",
        )

    assert result is True
    assert state_store.get_today_count() == 1
    mock_client.create_session.assert_called_once()

    active_sessions = state_store.get_active_sessions()
    # Initial insertion recorded before background poller completes or runs
    assert any(s["session_id"] == "sessions/sess-999" for s in active_sessions) or state_store.is_repo_completed("org/target-repo")


@pytest.mark.asyncio
async def test_resume_in_flight_sessions(state_store, mock_client):
    """Ensures incomplete sessions left in SQLite are recovered and polled."""
    state_store.record_session("sessions/dangling-1", "org/repo-1", status="IN_PROGRESS")
    state_store.record_session("sessions/dangling-2", "org/repo-2", status="PENDING")

    # Mock terminal response on poll
    mock_client.request_with_retry.side_effect = [
        {"state": "COMPLETED"},
        {"state": "FAILED"},
    ]

    orchestrator = JulesOrchestrator(
        client=mock_client,
        store=state_store,
        max_daily_quota=10,
        poll_interval_secs=0.01,
    )

    async with httpx.AsyncClient() as http_client:
        await orchestrator.resume_in_flight(http_client)

    # Both sessions should be removed from active state
    assert len(state_store.get_active_sessions()) == 0
    assert state_store.is_repo_completed("org/repo-1") is True
    assert state_store.is_repo_completed("org/repo-2") is False

@pytest.mark.asyncio
async def test_poll_session_api_exhaustion_marks_failed(state_store, mock_client):
    """Verifies that an unrecoverable request failure terminates polling and marks status FAILED."""
    state_store.record_session("sessions/failing-1", "org/repo-failing", status="IN_PROGRESS")

    # Simulate client giving up after max retries
    mock_client.request_with_retry.return_value = None

    orchestrator = JulesOrchestrator(
        client=mock_client,
        store=state_store,
        max_daily_quota=10,
        poll_interval_secs=0.01,
    )

    async with httpx.AsyncClient() as http_client:
        state = await orchestrator.poll_session(http_client, "sessions/failing-1")

    assert state == "FAILED"
    active = state_store.get_active_sessions()
    assert len(active) == 0
    assert state_store.is_repo_completed("org/repo-failing") is False
