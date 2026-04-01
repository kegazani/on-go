from __future__ import annotations

import uvicorn

from personalization_worker.api import create_app
from personalization_worker.config import Settings

app = create_app()


def run() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "personalization_worker.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.app_log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
