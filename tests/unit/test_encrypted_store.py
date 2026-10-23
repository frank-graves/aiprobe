"""Offline tests for EncryptedSessionStore."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from aiprobe.core.encrypted_store import EncryptedSessionStore
from aiprobe.core.session import Session, SessionStore


class MemoryStore(SessionStore):
    def __init__(self) -> None:
        self.data: dict[str, Session] = {}

    async def save(self, session: Session) -> None:
        self.data[session.target] = session

    async def load(self, target: str) -> Session | None:
        return self.data.get(target)

    async def delete(self, target: str) -> None:
        self.data.pop(target, None)


def make_session() -> Session:
    return Session(
        target="https://example.com",
        cookies={"secret": "token123"},
        user_agent="Mozilla/5.0",
        impersonate="chrome",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_encrypted_roundtrip() -> None:
    inner = MemoryStore()
    key = os.urandom(32)
    store = EncryptedSessionStore(inner, key)

    session = make_session()
    await store.save(session)

    # The inner store should not have the plaintext cookie
    raw = inner.data["https://example.com"]
    assert "secret" not in raw.cookies
    assert "__aiprobe_enc__" in raw.cookies

    loaded = await store.load("https://example.com")
    assert loaded is not None
    assert loaded.cookies == {"secret": "token123"}

    await store.delete("https://example.com")
    assert await store.load("https://example.com") is None
