"""docs.danidenada.dev

Sirve documentación en HTML desde esta misma carpeta.

Cada página es un HTML normal con su <title> y su <body>. El servidor extrae
el título y el contenido, y los inserta en el layout común (cabecera + menú
lateral). El menú se genera automáticamente con los .html de la carpeta y usa
el <title> de cada página como texto del enlace.

Recursos estáticos:
  /css/<archivo>.css
  /js/<archivo>.js
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

BASE_DIR = Path(__file__).resolve().parent
CSS_DIR = BASE_DIR / "css"
JS_DIR = BASE_DIR / "js"

SITE_URL = "https://www.danidenada.dev"
SITE_NAME = "danidenada.dev"

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
TITLE_SEPARATORS = (" · ", " | ", " — ", " - ", " – ")

app = FastAPI(
    title="docs.danidenada.dev",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _page_title(path: Path) -> str:
    try:
        text = _read_text(path)
    except OSError:
        return path.stem.replace("-", " ").replace("_", " ")

    match = TITLE_RE.search(text)
    if not match:
        return path.stem.replace("-", " ").replace("_", " ")

    title = html.unescape(TAG_RE.sub("", match.group(1))).strip()
    return title or path.stem.replace("-", " ").replace("_", " ")


def _menu_label(title: str) -> str:
    for separator in TITLE_SEPARATORS:
        if separator in title:
            title = title.split(separator, 1)[0]
    return title.strip() or "documento"


def _page_body(path: Path) -> str:
    text = _read_text(path)
    match = BODY_RE.search(text)
    return match.group(1).strip() if match else text


def _pages() -> list[dict[str, str]]:
    pages: list[dict[str, str]] = []
    try:
        entries = sorted(BASE_DIR.glob("*.html"), key=lambda item: item.name)
    except OSError:
        return pages

    for path in entries:
        if path.name == "index.html" or path.is_symlink() or not path.is_file():
            continue
        pages.append(
            {
                "name": path.name,
                "title": _page_title(path),
            }
        )
    return pages


def _render_menu(current: str) -> str:
    pages = _pages()
    links = [("/", "inicio", current == "index.html")]
    for page in pages:
        links.append(
            (
                f"/{page['name']}",
                _menu_label(page["title"]),
                page["name"] == current,
            )
        )

    items = []
    for href, label, active in links:
        classes = ' class="active" aria-current="page"' if active else ""
        items.append(
            f'<a href="{html.escape(href, quote=True)}"{classes}>'
            f"{html.escape(label)}</a>"
        )

    if not pages:
        items.append('<p class="docs-empty">Aún no hay documentos.</p>')

    return "\n".join(items)


def _render_page(filename: str, status_code: int = 200) -> HTMLResponse:
    path = BASE_DIR / filename
    if (
        path.is_symlink()
        or not path.is_file()
        or path.parent != BASE_DIR
        or path.suffix != ".html"
    ):
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    title = _page_title(path)
    body = _page_body(path)
    menu = _render_menu(filename)
    page_title = (
        f"Documentación · {SITE_NAME}"
        if filename == "index.html"
        else f"{_menu_label(title)} · docs.{SITE_NAME}"
    )

    page = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0f172a">
<meta name="description" content="Documentación técnica de danidenada.dev">
<link rel="icon" type="image/png" href="{SITE_URL}/img/favicon.png">
<title>{html.escape(page_title)}</title>
<link rel="stylesheet" href="/css/styles.css">
</head>
<body>
<a class="skip-link" href="#contenido">saltar al contenido</a>

<header class="site-header">
  <a class="brand" href="/">danidenada<span>.dev</span><small>docs</small></a>
  <div class="header-actions">
    <a class="header-link" href="{SITE_URL}/">sitio principal</a>
    <button class="menu-toggle" type="button" data-menu-toggle
            aria-controls="docs-sidebar" aria-expanded="false">documentos</button>
  </div>
</header>

<div class="docs-layout">
  <aside class="docs-sidebar" id="docs-sidebar" aria-label="Documentación">
    <p class="sidebar-title">documentación</p>
    <nav class="docs-nav">
{menu}
    </nav>
  </aside>

  <main class="docs-content" id="contenido">
{body}
  </main>
</div>

<footer class="footer">
  <p>© 2026 {SITE_NAME} · documentación técnica</p>
  <a class="footer-boton" href="{SITE_URL}/">sitio principal</a>
  <a class="footer-boton" href="https://download.danidenada.dev/">descargas</a>
</footer>

<script src="/js/docs.js" defer></script>
</body>
</html>"""
    return HTMLResponse(page, status_code=status_code)


def _safe_static(directory: Path, filename: str, suffix: str) -> Path:
    if (
        not filename
        or filename.startswith(".")
        or "\x00" in filename
        or "/" in filename
        or "\\" in filename
        or filename != Path(filename).name
        or not filename.endswith(suffix)
    ):
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    path = directory / filename
    if path.is_symlink() or not path.is_file():
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return path


@app.get("/css/{filename}", response_class=FileResponse)
def stylesheet(filename: str) -> FileResponse:
    path = _safe_static(CSS_DIR, filename, ".css")
    return FileResponse(
        path,
        media_type="text/css",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/js/{filename}", response_class=FileResponse)
def javascript(filename: str) -> FileResponse:
    path = _safe_static(JS_DIR, filename, ".js")
    return FileResponse(
        path,
        media_type="text/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return _render_page("index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    raise HTTPException(status_code=404, detail="Recurso no encontrado")


@app.get("/{filename}", response_class=HTMLResponse)
def document(filename: str) -> HTMLResponse:
    if filename == "index.html":
        return RedirectResponse(url="/", status_code=307)

    if not filename.endswith(".html"):
        candidate = BASE_DIR / f"{filename}.html"
        if (
            not candidate.is_symlink()
            and candidate.is_file()
            and candidate.parent == BASE_DIR
        ):
            return RedirectResponse(url=f"/{filename}.html", status_code=307)
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    return _render_page(filename)
