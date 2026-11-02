import logging
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import uvicorn
from starlette.routing import Host

from danideanda_api.api import app
from danideanda_api.updater import start_update_monitor


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


def _mount_app(module_name: str, relative_path: str, host: str) -> None:
    """Load a standalone FastAPI app and bind it to a single Host header."""
    path = BASE_DIR / relative_path
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        logger.error("Unable to load app %s from %s", module_name, path)
        return

    try:
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    except (FileNotFoundError, ImportError, SyntaxError):
        logger.exception("App %s could not be loaded", module_name)
        return

    app.router.routes.append(Host(host, app=module.app))
    logger.info("Mounted %s on %s", module_name, host)


def _mount_sites() -> None:
    _mount_app(
        "danideanda_download_main",
        "danideanda-download/main.py",
        "download.danidenada.dev",
    )
    _mount_app(
        "danideanda_docs_main",
        "danideanda-docs/main.py",
        "docs.danidenada.dev",
    )


_mount_sites()


def main() -> None:
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    logger.info("Starting the read-only API on %s:%s", host, port)
    start_update_monitor()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
