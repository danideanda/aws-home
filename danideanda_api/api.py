import hmac
import logging
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ValidationError


logger = logging.getLogger(__name__)
API_KEY_FILE = Path("/etc/aws-home/secrets/api.key")
STARTED_AT = time.monotonic()

app = FastAPI(
    title="aws-home API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class CommandRequest(BaseModel):
    command: Literal["estado", "hora", "version"]


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


@app.post("/api")
async def run_read_only_command(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> dict[str, str | float]:
    _authorize(x_api_key)

    try:
        command = CommandRequest.parse_obj(await request.json()).command
    except (ValueError, ValidationError):
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

    # CommandRequest's Literal prevents unlisted commands from reaching here.
    raise HTTPException(status_code=422, detail="Comando no permitido")
