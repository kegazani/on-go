from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from replay_service.errors import NotFoundError
from replay_service.models import ReplayRunOrchestrationMode, ReplayRunStatus


class ReplayRunRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, dict[str, Any]] = {}

    def create_run(
        self,
        session_id: str,
        orchestration_mode: ReplayRunOrchestrationMode,
        window_request: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        run_id = f"run-{uuid4().hex[:12]}"
        run = {
            "run_id": run_id,
            "session_id": session_id,
            "status": "created",
            "orchestration_mode": orchestration_mode,
            "window_request": window_request,
            "created_at_utc": now,
            "started_at_utc": None,
            "completed_at_utc": None,
            "failed_at_utc": None,
            "last_error": None,
            "window_count": 0,
            "sample_count": 0,
            "event_count": 0,
        }

        with self._lock:
            self._runs[run_id] = run

        return dict(run)

    def list_runs(self, session_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            runs = list(self._runs.values())

        if session_id is not None:
            runs = [run for run in runs if run["session_id"] == session_id]

        runs.sort(key=lambda run: run["created_at_utc"], reverse=True)
        return [dict(run) for run in runs]

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._runs.get(run_id)

        if run is None:
            raise NotFoundError(
                code="replay_run_not_found",
                message="Replay run was not found",
                details={"run_id": run_id},
            )

        return dict(run)

    def mark_running(self, run_id: str) -> dict[str, Any]:
        return self._update_status(run_id, status="running", timestamp_field="started_at_utc")

    def mark_completed(
        self,
        run_id: str,
        window_count: int,
        sample_count: int,
        event_count: int,
    ) -> dict[str, Any]:
        with self._lock:
            run = self._require_run(run_id)
            run["status"] = "completed"
            run["completed_at_utc"] = datetime.now(timezone.utc)
            run["window_count"] = window_count
            run["sample_count"] = sample_count
            run["event_count"] = event_count
            run["last_error"] = None
            return dict(run)

    def mark_failed(self, run_id: str, code: str, message: str) -> dict[str, Any]:
        with self._lock:
            run = self._require_run(run_id)
            run["status"] = "failed"
            run["failed_at_utc"] = datetime.now(timezone.utc)
            run["last_error"] = {"code": code, "message": message}
            return dict(run)

    def _update_status(
        self,
        run_id: str,
        status: ReplayRunStatus,
        timestamp_field: str,
    ) -> dict[str, Any]:
        with self._lock:
            run = self._require_run(run_id)
            run["status"] = status
            run[timestamp_field] = datetime.now(timezone.utc)
            return dict(run)

    def _require_run(self, run_id: str) -> dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError(
                code="replay_run_not_found",
                message="Replay run was not found",
                details={"run_id": run_id},
            )
        return run
