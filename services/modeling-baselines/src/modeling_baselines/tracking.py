from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class TrackingContext(Protocol):
    def log_params(self, params: dict[str, Any]) -> None: ...
    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None: ...
    def log_artifacts(self, local_dir: str | Path, artifact_path: str | None = None) -> None: ...
    def set_tag(self, key: str, value: Any) -> None: ...
    def set_tags(self, tags: dict[str, Any]) -> None: ...


class NoOpTracking:
    def log_params(self, params: dict[str, Any]) -> None:
        pass

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        pass

    def log_artifacts(self, local_dir: str | Path, artifact_path: str | None = None) -> None:
        pass

    def set_tag(self, key: str, value: Any) -> None:
        pass

    def set_tags(self, tags: dict[str, Any]) -> None:
        pass


def _flatten_metrics(obj: Any, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}{k}" if prefix else k
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[key] = float(v)
            elif isinstance(v, dict) and v and k not in ("confusion_matrix", "per_class_support", "labels"):
                nested = _flatten_metrics(v, prefix=f"{key}_")
                out.update(nested)
    return out


def create_mlflow_tracking(
    experiment_name: str = "on-go-modeling-baselines",
    tracking_uri: str | None = None,
    run_name: str | None = None,
    tags: dict[str, str] | None = None,
) -> tuple[Any, Any]:
    import mlflow

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.tracking.MlflowClient()
    exp = mlflow.set_experiment(experiment_name)
    run = mlflow.start_run(run_name=run_name, tags=tags or {})
    return run, client


def create_tracking_context(
    enabled: bool,
    experiment_name: str = "on-go-modeling-baselines",
    tracking_uri: str | None = None,
    run_name: str | None = None,
    tags: dict[str, str] | None = None,
) -> tuple[TrackingContext, Any]:
    if not enabled:
        return NoOpTracking(), None

    import mlflow

    run, client = create_mlflow_tracking(
        experiment_name=experiment_name,
        tracking_uri=tracking_uri,
        run_name=run_name,
        tags=tags,
    )

    class MlflowTrackingContext:
        def log_params(self, params: dict[str, Any]) -> None:
            mlflow.log_params({k: str(v) for k, v in params.items()})

        def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
            mlflow.log_metrics(metrics, step=step)

        def log_artifacts(self, local_dir: str | Path, artifact_path: str | None = None) -> None:
            mlflow.log_artifacts(str(local_dir), artifact_path=artifact_path)

        def set_tag(self, key: str, value: Any) -> None:
            mlflow.set_tag(key, str(value) if value is not None else "")

        def set_tags(self, tags: dict[str, Any]) -> None:
            mlflow.set_tags({k: str(v) for k, v in (tags or {}).items()})

    return MlflowTrackingContext(), run
