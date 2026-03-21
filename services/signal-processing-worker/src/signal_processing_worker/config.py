from __future__ import annotations

from dataclasses import dataclass
from os import getenv


def _as_bool(raw: str, default: bool) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass
class Settings:
    app_log_level: str
    database_dsn: str
    s3_endpoint_url: str
    s3_region: str
    s3_raw_bucket: str
    s3_clean_bucket: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_force_path_style: bool
    clean_root_prefix: str
    preprocessing_version: str
    gap_factor: float
    max_samples_per_stream: int
    persist_outputs: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_log_level=getenv("SPW_APP_LOG_LEVEL", "info"),
            database_dsn=getenv(
                "SPW_DATABASE_DSN",
                "postgresql://on_go:on_go@localhost:5432/on_go",
            ),
            s3_endpoint_url=getenv("SPW_S3_ENDPOINT_URL", "http://localhost:9000"),
            s3_region=getenv("SPW_S3_REGION", "us-east-1"),
            s3_raw_bucket=getenv("SPW_S3_RAW_BUCKET", "on-go-raw"),
            s3_clean_bucket=getenv("SPW_S3_CLEAN_BUCKET", "on-go-raw"),
            s3_access_key_id=getenv("SPW_S3_ACCESS_KEY_ID", "minioadmin"),
            s3_secret_access_key=getenv("SPW_S3_SECRET_ACCESS_KEY", "minioadmin"),
            s3_force_path_style=_as_bool(getenv("SPW_S3_FORCE_PATH_STYLE", "true"), default=True),
            clean_root_prefix=getenv("SPW_CLEAN_ROOT_PREFIX", "clean-sessions"),
            preprocessing_version=getenv("SPW_PREPROCESSING_VERSION", "e1-v1"),
            gap_factor=float(getenv("SPW_GAP_FACTOR", "1.8")),
            max_samples_per_stream=int(getenv("SPW_MAX_SAMPLES_PER_STREAM", "200000")),
            persist_outputs=_as_bool(getenv("SPW_PERSIST_OUTPUTS", "true"), default=True),
        )
