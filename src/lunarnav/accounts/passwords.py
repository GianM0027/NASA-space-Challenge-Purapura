# ABOUTME: Password hashing for LunarNav accounts (decision D45): scrypt from the standard library
# ABOUTME: Owner: Gian. Stored as "scrypt$n$r$p$salt$hash" (base64); constant-time comparison

"""Password hashing with scrypt (RFC 7914), no third-party dependency.

Parameters n=2**15, r=8, p=1 follow the OWASP Password Storage Cheat Sheet's scrypt baseline
(https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html): about 32 MiB
and a few tens of milliseconds per hash on this hardware.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
KEY_BYTES = 32
SALT_BYTES = 16
# scrypt needs 128 * n * r bytes (32 MiB here); allow headroom over that.
MAX_MEMORY_BYTES = 64 * 1024 * 1024


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=KEY_BYTES, maxmem=MAX_MEMORY_BYTES
    )


def hash_password(password: str) -> str:
    """Return the storable hash of ``password`` with a fresh random salt."""
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    """Return whether ``password`` matches ``stored`` (False for a malformed hash)."""
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(key)
        actual = _derive(password, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verified against when the username does not exist, so a wrong username takes as long as a
# wrong password.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
