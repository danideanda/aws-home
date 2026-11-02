import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse


logger = logging.getLogger(__name__)
DOCS_DIR = Path(__file__).resolve().parent / "docs"

app = FastAPI(
    title="aws-home Markdown",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/", response_class=PlainTextResponse)
def list_markdown_files() -> str:
    files = sorted(
        path.name
        for path in DOCS_DIR.iterdir()
        if (
            path.is_file()
            and not path.is_symlink()
            and not path.name.startswith(".")
            and path.suffix == ".md"
        )
    )
    return "\n".join(files)


@app.get("/{filename:path}", response_class=PlainTextResponse)
def get_raw_markdown(filename: str) -> PlainTextResponse:
    path = DOCS_DIR / filename
    if (
        not filename
        or path.name != filename
        or filename.startswith(".")
        or path.suffix != ".md"
        or path.is_symlink()
        or not path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("Could not read documentation file %s", path.name)
        raise HTTPException(
            status_code=500, detail="No se pudo leer el documento"
        ) from None

    return PlainTextResponse(content, media_type="text/markdown")
