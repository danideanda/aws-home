import hmac
import logging
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from danideanda_api import auth, monitoring, security


logger = logging.getLogger(__name__)
API_KEY_FILE = Path("/etc/aws-home/secrets/api.key")
STARTED_AT = time.monotonic()

app = FastAPI(
    title="aws-home API",
    version="1.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class CommandRequest(BaseModel):
    command: Literal["estado", "hora", "version", "monitor", "security"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def _read_api_key() -> str:
    try:
        key = API_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        logger.warning("API key file is unavailable")
        raise HTTPException(status_code=404, detail="Recurso no encontrado") from None

    if not key:
        logger.warning("API key file is empty")
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return key


def _authorize(api_key: str | None) -> None:
    expected_key = _read_api_key()
    if api_key is None or not hmac.compare_digest(
        api_key.encode("utf-8"), expected_key.encode("utf-8")
    ):
        raise HTTPException(status_code=404, detail="Recurso no encontrado")


def _validate(model: type[BaseModel], data: Any) -> BaseModel:
    validator = getattr(model, "model_validate", None)
    if validator is not None:
        return validator(data)
    return model.parse_obj(data)  # type: ignore[attr-defined]


@app.post("/api")
async def run_read_only_command(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Comandos de administración. Requieren X-API-Key; sin ella -> 404."""
    _authorize(x_api_key)

    try:
        command = _validate(CommandRequest, await request.json()).command
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(status_code=422, detail="Solicitud no válida") from None

    if command == "estado":
        return {
            "estado": "ok",
            "uptime_seconds": round(time.monotonic() - STARTED_AT, 2),
        }
    if command == "hora":
        return {"hora_utc": datetime.now(timezone.utc).isoformat()}
    if command == "version":
        return {"python": platform.python_version()}
    if command == "monitor":
        return {"monitor": monitoring.snapshot()}
    if command == "security":
        return {"security": security.snapshot()}

    # El Literal de CommandRequest impide llegar aquí con otro comando.
    raise HTTPException(status_code=422, detail="Comando no permitido")


@app.post("/api/login")
async def login(payload: LoginRequest) -> dict[str, Any]:
    """Login para el sistema de cursos. Credenciales malas -> 404."""
    if not auth.authenticate(payload.username, payload.password):
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    issued = auth.issue_token(payload.username)
    if issued is None:
        logger.error("No se pudo emitir token: falta la clave de sesión")
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    token, ttl = issued
    return {
        "token": token,
        "token_type": "Bearer",
        "expires_in": ttl,
        "username": payload.username,
    }
