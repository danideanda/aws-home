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


def _mount_docs_site() -> None:
    docs_main = Path(__file__).resolve().parent / "danideanda-docs" / "main.py"
    spec = spec_from_file_location("danideanda_docs_main", docs_main)
    if spec is None or spec.loader is None:
        logger.error("Unable to load documentation app from %s", docs_main)
        return

    try:
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    except (FileNotFoundError, ImportError, SyntaxError):
        logger.exception("Documentation app could not be loaded")
        return
    app.router.routes.append(Host("docs.danidenada.dev", app=module.app))


_mount_docs_site()


def main() -> None:
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    logger.info("Starting the read-only API on %s:%s", host, port)
    start_update_monitor()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
