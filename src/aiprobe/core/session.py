"""Session lifecycle and persistence."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from aiprobe.core.http import HttpClient


class Session(BaseModel):
    """Immutable snapshot of a scraping session context."""

    model_config = ConfigDict(frozen=True)

    target: str
    cookies: dict[str, str] = Field(default_factory=dict)
    user_agent: str
    impersonate: str = "chrome"
    proxy: str | None = None
    created_at: datetime
    expires_at: datetime | None = None

    def is_expired(self) -> bool:
        """Return True if the session has an expiry and it's in the past."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    def cookie_names(self) -> list[str]:
        """Return the names of all cookies in this session."""
        return list(self.cookies.keys())

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Session:
        """Deserialize from a dictionary."""
        return cls.model_validate(data)


class SessionStore(Protocol):
    """Abstract persistence backend for sessions."""

    async def save(self, session: Session) -> None: ...

    async def load(self, target: str) -> Session | None: ...

    async def delete(self, target: str) -> None: ...


class FileSessionStore:
    """Persists sessions as JSON files in a local directory."""

    def __init__(self, directory: str | Path = ".aiprobe/sessions") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _sanitize_target(self, target: str) -> str:
        """Convert a target URL into a safe filename."""
        base = re.sub(r"[^a-zA-Z0-9_\-]", "_", target)
        import hashlib

        h = hashlib.sha256(target.encode()).hexdigest()[:8]
        return f"{base}_{h}"

    def _path_for(self, target: str) -> Path:
        return self.directory / f"{self._sanitize_target(target)}.json"

    async def save(self, session: Session) -> None:
        """Atomic write to disk."""
        path = self._path_for(session.target)
        data = json.dumps(session.to_dict(), indent=2)

        fd, tmp_path = tempfile.mkstemp(dir=self.directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp_path, path)
        except Exception:
            os.unlink(tmp_path)
            raise

    async def load(self, target: str) -> Session | None:
        """Load a session if the file exists."""
        path = self._path_for(target)
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
            return Session.from_dict(json.loads(text))
        except (json.JSONDecodeError, ValueError):
            return None

    async def delete(self, target: str) -> None:
        """Remove a session file."""
        path = self._path_for(target)
        if path.exists():
            path.unlink()


RefreshHook = Callable[[str], Awaitable[Session]]
ClientFactory = Callable[[Session], HttpClient]


class SessionManager:
    """Orchestrates session retrieval, expiration, and refresh."""

    def __init__(
        self,
        store: SessionStore,
        client_factory: ClientFactory,
    ) -> None:
        self.store = store
        self.client_factory = client_factory
        self._refresh_hook: RefreshHook | None = None

    def set_refresh_hook(self, hook: RefreshHook) -> None:
        """Register a callback to handle session refresh."""
        self._refresh_hook = hook

    async def get_or_create(self, target: str, **defaults: object) -> Session:
        """Return an existing valid session or create a new one."""
        session = await self.store.load(target)

        if session and not session.is_expired():
            return session

        if self._refresh_hook:
            new_session = await self._refresh_hook(target)
            await self.store.save(new_session)
            return new_session

        now = datetime.now(UTC)
        new_session = Session(
            target=target,
            cookies={},
            user_agent=str(defaults.get("user_agent", "aiprobe/0.1")),
            impersonate=str(defaults.get("impersonate", "chrome")),
            proxy=defaults.get("proxy") if isinstance(defaults.get("proxy"), str) else None,
            created_at=now,
            expires_at=None,
        )
        await self.store.save(new_session)
        return new_session

    async def refresh(self, target: str) -> Session:
        """Force a refresh of the session."""
        if not self._refresh_hook:
            raise RuntimeError("No refresh hook registered.")
        new_session = await self._refresh_hook(target)
        await self.store.save(new_session)
        return new_session

    async def client_for(self, session: Session) -> HttpClient:
        """Build an HTTP client configured with the session's parameters."""
        client = self.client_factory(session)
        return client
