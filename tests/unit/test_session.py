"""Offline tests for session management and persistence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aiprobe.core.http import HttpClient, HttpResponse
from aiprobe.core.session import (
    FileSessionStore,
    Session,
    SessionManager,
    SessionStore,
)


class MemoryStore(SessionStore):
    def __init__(self) -> None:
        self.data: dict[str, Session] = {}

    async def save(self, session: Session) -> None:
        self.data[session.target] = session

    async def load(self, target: str) -> Session | None:
        return self.data.get(target)

    async def delete(self, target: str) -> None:
        self.data.pop(target, None)


class FakeClient(HttpClient):
    async def request(self, method: str, url: str, **kwargs: object) -> HttpResponse:
        raise NotImplementedError

    async def get(self, url: str, **kwargs: object) -> HttpResponse:
        raise NotImplementedError

    async def post(self, url: str, **kwargs: object) -> HttpResponse:
        raise NotImplementedError

    async def stream(self, method: str, url: str, **kwargs: object) -> AsyncIterator[bytes]:
        raise NotImplementedError

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass


def _make_session(target: str, expires_in: timedelta | None = None) -> Session:
    now = datetime.now(UTC)
    exp = (now + expires_in) if expires_in else None
    return Session(
        target=target,
        cookies={"cf_clearance": "abc"},
        user_agent="Mozilla/5.0",
        impersonate="chrome",
        created_at=now,
        expires_at=exp,
    )


def test_session_serialization() -> None:
    s = _make_session("https://example.com")
    d = s.to_dict()
    s2 = Session.from_dict(d)
    assert s == s2


def test_session_expiry() -> None:
    s1 = _make_session("https://example.com", timedelta(hours=1))
    assert not s1.is_expired()

    s2 = _make_session("https://example.com", timedelta(hours=-1))
    assert s2.is_expired()

    s3 = _make_session("https://example.com", None)
    assert not s3.is_expired()


@pytest.mark.asyncio
async def test_file_session_store(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    s = _make_session("https://example.com/weird?path=1")

    await store.save(s)
    loaded = await store.load("https://example.com/weird?path=1")
    assert loaded == s

    # Check filename sanitization (should not contain ? or /)
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert "?" not in files[0].name
    assert "/" not in files[0].name
    assert ":" not in files[0].name

    await store.delete("https://example.com/weird?path=1")
    assert await store.load("https://example.com/weird?path=1") is None


@pytest.mark.asyncio
async def test_manager_reuses_valid_session() -> None:
    store = MemoryStore()
    manager = SessionManager(store, lambda s: FakeClient())

    s_valid = _make_session("https://example.com", timedelta(hours=1))
    await store.save(s_valid)

    refresh_called = False

    async def dummy_refresh(target: str) -> Session:
        nonlocal refresh_called
        refresh_called = True
        return _make_session(target)

    manager.set_refresh_hook(dummy_refresh)

    result = await manager.get_or_create("https://example.com")
    assert result == s_valid
    assert not refresh_called


@pytest.mark.asyncio
async def test_manager_refreshes_expired_session() -> None:
    store = MemoryStore()
    manager = SessionManager(store, lambda s: FakeClient())

    s_expired = _make_session("https://example.com", timedelta(hours=-1))
    await store.save(s_expired)

    refresh_called = False

    async def dummy_refresh(target: str) -> Session:
        nonlocal refresh_called
        refresh_called = True
        return _make_session(target)

    manager.set_refresh_hook(dummy_refresh)

    result = await manager.get_or_create("https://example.com")
    assert result != s_expired
    assert refresh_called
    assert not result.is_expired()
