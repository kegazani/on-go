from __future__ import annotations

import uvicorn

from ingest_api.api import create_app
from ingest_api.config import Settings

app = create_app()


def run() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "ingest_api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.app_log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
