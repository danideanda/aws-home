"""Autenticación de alumnos del sistema de cursos y tokens de sesión.

Todo con la biblioteca estándar: scrypt para contraseñas y HMAC-SHA256 para
firmar los tokens. Sin dependencias externas.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

USERS_FILE = Path("/etc/aws-home/secrets/courses.json")
SESSION_KEY_FILE = Path("/etc/aws-home/secrets/session.key")

TOKEN_TTL_SECONDS = int(os.getenv("COURSE_TOKEN_TTL_SECONDS", "43200"))

# Parámetros de scrypt: seguros y rápidos en 2 vCPU.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, salt: bytes | None = None) -> dict[str, Any]:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return {
        "salt": salt.hex(),
        "hash": derived.hex(),
        "n": _SCRYPT_N,
        "r": _SCRYPT_R,
        "p": _SCRYPT_P,
    }


def verify_password(password: str, record: dict[str, Any]) -> bool:
    try:
        salt = bytes.fromhex(str(record["salt"]))
        expected = bytes.fromhex(str(record["hash"]))
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(record.get("n", _SCRYPT_N)),
            r=int(record.get("r", _SCRYPT_R)),
            p=int(record.get("p", _SCRYPT_P)),
            dklen=len(expected) or _SCRYPT_DKLEN,
        )
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(derived, expected)


def load_users() -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    users = raw.get("users") if isinstance(raw, dict) else None
    if not isinstance(users, dict):
        return {}
    return {str(name): record for name, record in users.items() if isinstance(record, dict)}


def authenticate(username: str, password: str) -> bool:
    """Devuelve True solo si el usuario existe y la contraseña coincide."""
    record = load_users().get(username)
    if record is None:
        # Deriva igualmente para no filtrar por tiempo si el usuario existe.
        verify_password(password, hash_password(password))
        return False
    return verify_password(password, record)


def _session_key() -> bytes | None:
    try:
        key = SESSION_KEY_FILE.read_bytes().strip()
    except OSError:
        return None
    return key or None


def issue_token(username: str) -> tuple[str, int] | None:
    """Emite un token firmado. Devuelve None si falta la clave de sesión."""
    key = _session_key()
    if key is None:
        return None

    payload = {
        "u": username,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "n": _b64encode(secrets.token_bytes(8)),
    }
    body = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _b64encode(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}", TOKEN_TTL_SECONDS


def verify_token(token: str | None) -> str | None:
    """Devuelve el usuario si el token es válido y no ha caducado."""
    if not token or "." not in token:
        return None

    key = _session_key()
    if key is None:
        return None

    body, _, signature = token.partition(".")
    expected = _b64encode(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(_b64decode(body))
        if int(payload["exp"]) < int(time.time()):
            return None
        username = payload["u"]
    except (KeyError, TypeError, ValueError):
        return None

    return username if isinstance(username, str) else None
