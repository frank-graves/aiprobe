"""Offline tests for AES-256-GCM crypto."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from aiprobe.utils import crypto


def test_encrypt_decrypt_roundtrip() -> None:
    key = os.urandom(32)
    plaintext = b"secret session data"
    blob = crypto.encrypt(plaintext, key)
    assert crypto.decrypt(blob, key) == plaintext


def test_wrong_key() -> None:
    key1 = os.urandom(32)
    key2 = os.urandom(32)
    blob = crypto.encrypt(b"hello", key1)
    with pytest.raises(ValueError, match="Decryption failed"):
        crypto.decrypt(blob, key2)


def test_tampered_blob() -> None:
    key = os.urandom(32)
    blob = bytearray(crypto.encrypt(b"hello", key))
    blob[-1] ^= 0xFF  # flip a bit in ciphertext
    with pytest.raises(ValueError, match="Decryption failed"):
        crypto.decrypt(bytes(blob), key)


def test_generate_and_load_key(tmp_path: Path) -> None:
    key_path = tmp_path / "test.key"
    crypto.generate_key(key_path)
    assert key_path.exists()

    # Check permissions (Unix only)
    if os.name != "nt":
        mode = key_path.stat().st_mode
        assert mode & stat.S_IRWXG == 0
        assert mode & stat.S_IRWXO == 0

    loaded = crypto.load_key(key_path)
    assert len(loaded) == 32
