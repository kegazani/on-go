from __future__ import annotations

from pathlib import Path


class Settings:
    def __init__(
        self,
        app_host: str = "0.0.0.0",
        app_port: int = 8100,
        app_log_level: str = "info",
        model_dir: Path | None = None,
        valence_scoped_policy_path: Path | None = None,
        valence_canary_state_path: Path | None = None,
        valence_dashboard_snapshot_path: Path | None = None,
        valence_dashboard_freshness_slo_minutes: int = 120,
    ) -> None:
        self.app_host = app_host
        self.app_port = app_port
        self.app_log_level = app_log_level
        self.model_dir = model_dir
        self.valence_scoped_policy_path = valence_scoped_policy_path
        self.valence_canary_state_path = valence_canary_state_path
        self.valence_dashboard_snapshot_path = valence_dashboard_snapshot_path
        self.valence_dashboard_freshness_slo_minutes = valence_dashboard_freshness_slo_minutes

    @classmethod
    def from_env(cls) -> "Settings":
        import os

        model_dir = os.environ.get("INFERENCE_MODEL_DIR")
        policy_path = os.environ.get("INFERENCE_VALENCE_SCOPED_POLICY_PATH")
        canary_state_path = os.environ.get("INFERENCE_VALENCE_CANARY_STATE_PATH")
        dashboard_snapshot_path = os.environ.get("INFERENCE_VALENCE_DASHBOARD_SNAPSHOT_PATH")
        return cls(
            app_host=os.environ.get("INFERENCE_APP_HOST", "0.0.0.0"),
            app_port=int(os.environ.get("INFERENCE_APP_PORT", "8100")),
            app_log_level=os.environ.get("INFERENCE_APP_LOG_LEVEL", "info"),
            model_dir=Path(model_dir) if model_dir else None,
            valence_scoped_policy_path=Path(policy_path) if policy_path else None,
            valence_canary_state_path=Path(canary_state_path) if canary_state_path else None,
            valence_dashboard_snapshot_path=Path(dashboard_snapshot_path) if dashboard_snapshot_path else None,
            valence_dashboard_freshness_slo_minutes=int(
                os.environ.get("INFERENCE_VALENCE_DASHBOARD_FRESHNESS_SLO_MINUTES", "120")
            ),
        )
