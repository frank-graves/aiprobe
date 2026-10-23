import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

KEY_SIZE = 32
NONCE_SIZE = 12
SALT_SIZE = 16
TAG_SIZE = 16


def generate_key(path: str | Path) -> None:
    key = os.urandom(KEY_SIZE)
    p = Path(path)
    p.write_bytes(key)
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)


def load_key(path: str | Path) -> bytes:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Encryption key not found at {p}")
    return p.read_bytes()


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_SIZE, n=2**14, r=8, p=1)
    return kdf.derive(passphrase.encode())


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    ct_and_tag = aesgcm.encrypt(nonce, plaintext, None)
    tag = ct_and_tag[-TAG_SIZE:]
    ciphertext = ct_and_tag[:-TAG_SIZE]
    return salt + nonce + tag + ciphertext


def decrypt(blob: bytes, key: bytes) -> bytes:
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")
    if len(blob) < SALT_SIZE + NONCE_SIZE + TAG_SIZE:
        raise ValueError("Blob is too short to be valid")
    nonce = blob[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    tag = blob[SALT_SIZE + NONCE_SIZE : SALT_SIZE + NONCE_SIZE + TAG_SIZE]
    ciphertext = blob[SALT_SIZE + NONCE_SIZE + TAG_SIZE :]
    ct_and_tag = ciphertext + tag
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ct_and_tag, None)
    except Exception as exc:
        raise ValueError("Decryption failed: blob was tampered or key is incorrect") from exc
