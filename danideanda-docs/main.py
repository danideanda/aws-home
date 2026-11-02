"""docs.danidenada.dev

La documentacion vive en disco en `download/docs/` y se sirve publicamente
desde `download.danidenada.dev/docs/`. Este host muestra una pagina HTML con
los datos de ese sitio de descargas.
"""

from __future__ import annotations

import html
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse


BASE_DIR = Path(__file__).resolve().parents[1]
DOWNLOAD_DIR = BASE_DIR / "download"
DOCS_DIR = DOWNLOAD_DIR / "docs"
STUDY_DIR = DOWNLOAD_DIR / "study"
PUBLIC_URL = "https://download.danidenada.dev"

app = FastAPI(
    title="docs.danidenada.dev",
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


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    docs = _markdown_files(DOCS_DIR)
    study = _markdown_files(STUDY_DIR)

    rows = "".join(
        "<tr>"
        f'<td><a href="{PUBLIC_URL}/docs/{html.escape(item.name)}">{html.escape(item.name)}</a></td>'
        f"<td>{_human_size(item.stat().st_size)}</td>"
        "</tr>"
        for item in docs
    ) or '<tr><td colspan="2"><em>sin documentos</em></td></tr>'

    page = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Documentaci&oacute;n &middot; danidenada.dev</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 46rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.55; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid rgba(127,127,127,.3); }}
  code {{ background: rgba(127,127,127,.18); padding: .15rem .35rem; border-radius: .25rem; }}
</style>
</head>
<body>
<h1>Documentaci&oacute;n</h1>
<p>Este contenido se sirve desde
<a href="{PUBLIC_URL}/">{PUBLIC_URL}</a>.</p>

<h2>Documentos p&uacute;blicos</h2>
<table>
<thead><tr><th>Documento</th><th>Tama&ntilde;o</th></tr></thead>
<tbody>{rows}</tbody>
</table>

<h2>Material de estudio</h2>
<p>{len(study)} documento(s). Requiere sesi&oacute;n:
<code>Authorization: Bearer &lt;token&gt;</code> obtenido en
<code>POST https://api.danidenada.dev/api/login</code>.</p>
</body>
</html>"""
    return HTMLResponse(page)


@app.get("/{filename:path}")
def legacy_document(filename: str) -> RedirectResponse:
    """Redirige enlaces antiguos /<archivo>.md al nuevo host."""
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

    target = DOCS_DIR / filename
    if target.is_symlink() or not target.is_file():
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    return RedirectResponse(
        url=f"{PUBLIC_URL}/docs/{filename}", status_code=307
    )
