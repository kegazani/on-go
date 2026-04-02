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
    s3_presign_endpoint_url: str | None
    s3_region: str
    s3_bucket: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_force_path_style: bool
    s3_presign_ttl_seconds: int
    s3_presign_require_https: bool

    @classmethod
    def from_env(cls) -> "Settings":
        presign_url = getenv("INGEST_S3_PRESIGN_ENDPOINT_URL") or None
        return cls(
            app_host=getenv("INGEST_APP_HOST", "0.0.0.0"),
            app_port=int(getenv("INGEST_APP_PORT", "8080")),
            app_log_level=getenv("INGEST_APP_LOG_LEVEL", "info"),
            database_dsn=getenv(
                "INGEST_DATABASE_DSN",
                "postgresql://on_go:on_go@localhost:5432/on_go",
            ),
            s3_endpoint_url=getenv("INGEST_S3_ENDPOINT_URL", "http://localhost:9000"),
            s3_presign_endpoint_url=presign_url,
            s3_region=getenv("INGEST_S3_REGION", "us-east-1"),
            s3_bucket=getenv("INGEST_S3_BUCKET", "on-go-raw"),
            s3_access_key_id=getenv("INGEST_S3_ACCESS_KEY_ID", "minioadmin"),
            s3_secret_access_key=getenv("INGEST_S3_SECRET_ACCESS_KEY", "minioadmin"),
            s3_force_path_style=getenv("INGEST_S3_FORCE_PATH_STYLE", "true").lower() in {"1", "true", "yes"},
            s3_presign_ttl_seconds=int(getenv("INGEST_S3_PRESIGN_TTL_SECONDS", "900")),
            s3_presign_require_https=getenv("INGEST_S3_PRESIGN_REQUIRE_HTTPS", "").lower()
            in {"1", "true", "yes"},
        )
