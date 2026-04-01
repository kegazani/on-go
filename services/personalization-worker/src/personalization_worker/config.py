from __future__ import annotations


class Settings:
    def __init__(
        self,
        app_host: str = "0.0.0.0",
        app_port: int = 8110,
        app_log_level: str = "info",
    ) -> None:
        self.app_host = app_host
        self.app_port = app_port
        self.app_log_level = app_log_level

    @classmethod
    def from_env(cls) -> "Settings":
        import os

        return cls(
            app_host=os.environ.get("PERSONALIZATION_APP_HOST", "0.0.0.0"),
            app_port=int(os.environ.get("PERSONALIZATION_APP_PORT", "8110")),
            app_log_level=os.environ.get("PERSONALIZATION_APP_LOG_LEVEL", "info"),
        )
