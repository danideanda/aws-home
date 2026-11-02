"""download.danidenada.dev

Expone:
  GET /                 -> indice HTML
  GET /docs/<file>.md   -> documentacion publica
  GET /study/<file>.md  -> material privado, exige token Bearer valido

Cualquier acceso no autorizado responde 404, igual que un recurso inexistente.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from danideanda_api.auth import verify_token


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "download"
DOCS_DIR = DATA_DIR / "docs"
STUDY_DIR = DATA_DIR / "study"

app = FastAPI(
    title="download.danidenada.dev",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _markdown_files(directory: Path) -> list[Path]:
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name)
    except OSError:
        return []
    return [
        entry
        for entry in entries
        if entry.is_file()
        and not entry.is_symlink()
        and not entry.name.startswith(".")
        and entry.suffix == ".md"
    ]


def _resolve(directory: Path, filename: str) -> Path:
    """Devuelve la ruta segura o lanza 404 (sin traversal ni symlinks)."""
    if (
        not filename
        or filename.startswith(".")
        or "\x00" in filename
        or "/" in filename
        or "\\" in filename
        or filename != Path(filename).name
        or not filename.endswith(".md")
    ):
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    path = directory / filename
    if path.is_symlink() or not path.is_file():
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        raise HTTPException(status_code=404, detail="Recurso no encontrado") from None


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    docs = _markdown_files(DOCS_DIR)
    study = _markdown_files(STUDY_DIR)

    rows = "".join(
        f'<li><a href="/docs/{html.escape(item.name)}">{html.escape(item.name)}</a></li>'
        for item in docs
    ) or "<li><em>sin documentos</em></li>"

    page = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>download.danidenada.dev</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 46rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.55; }}
  code {{ background: rgba(127,127,127,.18); padding: .15rem .35rem; border-radius: .25rem; }}
  h2 {{ margin-top: 2rem; border-bottom: 1px solid rgba(127,127,127,.3); padding-bottom: .3rem; }}
</style>
</head>
<body>
<h1>download.danidenada.dev</h1>

<h2>Documentaci&oacute;n p&uacute;blica</h2>
<ul>{rows}</ul>

<h2>Material de estudio</h2>
<p>{len(study)} documento(s) disponible(s). El acceso requiere una sesi&oacute;n v&aacute;lida:
<code>Authorization: Bearer &lt;token&gt;</code></p>
<p>Obt&eacute;n el token con <code>POST https://api.danidenada.dev/api/login</code>.</p>
</body>
</html>"""
    return HTMLResponse(page)


@app.get("/docs/{filename:path}", response_class=PlainTextResponse)
def public_document(filename: str) -> PlainTextResponse:
    path = _resolve(DOCS_DIR, filename)
    return PlainTextResponse(_read(path), media_type="text/markdown")


@app.get("/study/{filename:path}", response_class=PlainTextResponse)
def study_document(
    filename: str,
    authorization: str | None = Header(default=None),
) -> PlainTextResponse:
    token: str | None = None
    if authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = credentials.strip()

    if verify_token(token) is None:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    path = _resolve(STUDY_DIR, filename)
    return PlainTextResponse(_read(path), media_type="text/markdown")
