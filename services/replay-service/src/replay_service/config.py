from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass
class Settings:
    app_host: str
    app_port: int
    app_log_level: str
    database_dsn: str
    s3_endpoint_url: str
    s3_region: str
    s3_bucket: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_force_path_style: bool
    default_window_ms: int
    max_window_ms: int
    max_samples_per_stream: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_host=getenv("REPLAY_APP_HOST", "0.0.0.0"),
            app_port=int(getenv("REPLAY_APP_PORT", "8090")),
            app_log_level=getenv("REPLAY_APP_LOG_LEVEL", "info"),
            database_dsn=getenv(
                "REPLAY_DATABASE_DSN",
                "postgresql://on_go:on_go@localhost:5432/on_go",
            ),
            s3_endpoint_url=getenv("REPLAY_S3_ENDPOINT_URL", "http://localhost:9000"),
            s3_region=getenv("REPLAY_S3_REGION", "us-east-1"),
            s3_bucket=getenv("REPLAY_S3_BUCKET", "on-go-raw"),
            s3_access_key_id=getenv("REPLAY_S3_ACCESS_KEY_ID", "minioadmin"),
            s3_secret_access_key=getenv("REPLAY_S3_SECRET_ACCESS_KEY", "minioadmin"),
            s3_force_path_style=getenv("REPLAY_S3_FORCE_PATH_STYLE", "true").lower() in {"1", "true", "yes"},
            default_window_ms=int(getenv("REPLAY_DEFAULT_WINDOW_MS", "5000")),
            max_window_ms=int(getenv("REPLAY_MAX_WINDOW_MS", "600000")),
            max_samples_per_stream=int(getenv("REPLAY_MAX_SAMPLES_PER_STREAM", "2000")),
        )
