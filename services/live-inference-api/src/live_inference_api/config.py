from __future__ import annotations

from pathlib import Path


class Settings:
    def __init__(
        self,
        app_host: str = "0.0.0.0",
        app_port: int = 8120,
        app_log_level: str = "info",
        model_dir: Path | None = None,
        window_size_ms: int = 15000,
        step_size_ms: int = 5000,
        heart_staleness_ms: int = 120_000,
        replay_service_base_url: str = "http://localhost:8090",
    ) -> None:
        self.app_host = app_host
        self.app_port = app_port
        self.app_log_level = app_log_level
        self.model_dir = model_dir
        self.window_size_ms = window_size_ms
        self.step_size_ms = step_size_ms
        self.heart_staleness_ms = heart_staleness_ms
        self.replay_service_base_url = replay_service_base_url

    @classmethod
    def from_env(cls) -> "Settings":
        import os

        model_dir = os.environ.get("LIVE_INFERENCE_MODEL_DIR") or os.environ.get("INFERENCE_MODEL_DIR")
        window_ms = int(os.environ.get("LIVE_INFERENCE_WINDOW_MS", "15000"))
        staleness_raw = os.environ.get("LIVE_INFERENCE_HEART_STALENESS_MS")
        if staleness_raw is not None and staleness_raw.strip():
            heart_staleness_ms = int(staleness_raw)
        else:
            heart_staleness_ms = max(120_000, window_ms * 6)
        return cls(
            app_host=os.environ.get("LIVE_INFERENCE_APP_HOST", "0.0.0.0"),
            app_port=int(os.environ.get("LIVE_INFERENCE_APP_PORT", "8120")),
            app_log_level=os.environ.get("LIVE_INFERENCE_APP_LOG_LEVEL", "info"),
            model_dir=Path(model_dir) if model_dir else None,
            window_size_ms=window_ms,
            step_size_ms=int(os.environ.get("LIVE_INFERENCE_STEP_MS", "5000")),
            heart_staleness_ms=heart_staleness_ms,
            replay_service_base_url=os.environ.get("REPLAY_SERVICE_BASE_URL", "http://localhost:8090"),
        )
