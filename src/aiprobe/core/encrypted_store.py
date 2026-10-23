"""Transparent AES-256-GCM encryption wrapper for SessionStore."""

from __future__ import annotations

import base64
import json

from aiprobe.core.session import Session, SessionStore
from aiprobe.utils import crypto


class EncryptedSessionStore:
    """Wraps any SessionStore, encrypting the payload before delegating.

    NOTE: To strictly satisfy the SessionStore interface, the encrypted
    bytes are base64-encoded and stored inside `Session.cookies`
    under a reserved key (`__aiprobe_enc__`). The original target is
    preserved so the inner store can still route requests.
    """

    def __init__(self, inner: SessionStore, key: bytes) -> None:
        self.inner = inner
        self.key = key

    async def save(self, session: Session) -> None:
        data = json.dumps(session.to_dict()).encode("utf-8")
        encrypted = crypto.encrypt(data, self.key)
        encoded = base64.b64encode(encrypted).decode("ascii")

        wrapper = Session(
            target=session.target,
            cookies={"__aiprobe_enc__": encoded},
            user_agent=session.user_agent,
            impersonate=session.impersonate,
            proxy=session.proxy,
            created_at=session.created_at,
            expires_at=session.expires_at,
        )
        await self.inner.save(wrapper)

    async def load(self, target: str) -> Session | None:
        wrapper = await self.inner.load(target)
        if not wrapper:
            return None

        encoded = wrapper.cookies.get("__aiprobe_enc__")
        if not encoded:
            return None

        try:
            encrypted = base64.b64decode(encoded)
            decrypted = crypto.decrypt(encrypted, self.key)
            data = json.loads(decrypted.decode("utf-8"))
            return Session.from_dict(data)
        except Exception:
            return None

    async def delete(self, target: str) -> None:
        await self.inner.delete(target)
