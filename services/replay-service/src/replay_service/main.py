from __future__ import annotations

import uvicorn

from replay_service.api import create_app
from replay_service.config import Settings

app = create_app()


def run() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "replay_service.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.app_log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
