from __future__ import annotations

import json
from typing import Iterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from replay_service.config import Settings
from replay_service.db import Database
from replay_service.errors import ApiError
from replay_service.models import (
    ErrorResponse,
    ReplayManifestResponse,
    ReplayRunListResponse,
    ReplayRunRequest,
    ReplayRunState,
    ReplayWindowRequest,
    ReplayWindowResponse,
)
from replay_service.run_registry import ReplayRunRegistry
from replay_service.service import ReplayService
from replay_service.storage import S3Storage


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    database = Database(cfg.database_dsn)
    storage = S3Storage(cfg)
    service = ReplayService(
        database=database,
        storage=storage,
        default_window_ms=cfg.default_window_ms,
        max_window_ms=cfg.max_window_ms,
        max_samples_per_stream=cfg.max_samples_per_stream,
    )
    run_registry = ReplayRunRegistry()

    app = FastAPI(
        title="On-Go Replay Service",
        version="0.1.0",
        description="Replay raw session data from Postgres metadata + MinIO/S3 artifacts.",
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        response = ErrorResponse(error={"code": exc.code, "message": exc.message, "details": exc.details})
        return JSONResponse(status_code=exc.status_code, content=response.model_dump(mode="json"))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/replay/sessions/{session_id}/manifest", response_model=ReplayManifestResponse)
    async def replay_manifest(session_id: str) -> ReplayManifestResponse:
        return service.get_manifest(session_id)

    @app.post("/v1/replay/sessions/{session_id}/windows", response_model=ReplayWindowResponse)
    async def replay_window(session_id: str, payload: ReplayWindowRequest) -> ReplayWindowResponse:
        return service.get_window(session_id=session_id, request=payload)

    @app.post("/v1/replay/sessions/{session_id}/runs", response_model=ReplayRunState)
    async def create_replay_run(session_id: str, payload: ReplayRunRequest) -> ReplayRunState:
        # Validate that the target session is replay-ready before registering a run.
        service.get_manifest(session_id)
        run = run_registry.create_run(
            session_id=session_id,
            orchestration_mode=payload.orchestration_mode,
            window_request=payload.window_request.model_dump(mode="json"),
        )
        return ReplayRunState.model_validate(run)

    @app.get("/v1/replay/runs", response_model=ReplayRunListResponse)
    async def list_replay_runs(session_id: str | None = None) -> ReplayRunListResponse:
        runs = run_registry.list_runs(session_id=session_id)
        return ReplayRunListResponse(runs=[ReplayRunState.model_validate(run) for run in runs])

    @app.get("/v1/replay/runs/{run_id}", response_model=ReplayRunState)
    async def get_replay_run(run_id: str) -> ReplayRunState:
        return ReplayRunState.model_validate(run_registry.get_run(run_id))

    @app.get("/v1/replay/runs/{run_id}/events")
    async def stream_replay_run(run_id: str) -> StreamingResponse:
        run = ReplayRunState.model_validate(run_registry.get_run(run_id))
        run_registry.mark_running(run_id)

        def _emit(event_name: str, payload: dict) -> str:
            return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"

        def event_stream() -> Iterator[str]:
            window_count = 0
            sample_count = 0
            event_count = 0

            try:
                windows, _ = service.iterate_windows(
                    session_id=run.session_id,
                    request=run.window_request,
                    orchestration_mode=run.orchestration_mode,
                )
                for window in windows:
                    window_count += 1
                    sample_count += window.sample_count
                    event_count += window.event_count
                    yield _emit("replay_window", window.model_dump(mode="json"))

                completed = run_registry.mark_completed(
                    run_id=run_id,
                    window_count=window_count,
                    sample_count=sample_count,
                    event_count=event_count,
                )
                yield _emit("run_completed", ReplayRunState.model_validate(completed).model_dump(mode="json"))
            except Exception as exc:  # pragma: no cover - runtime fallback path
                failed = run_registry.mark_failed(
                    run_id=run_id,
                    code="replay_run_failed",
                    message=str(exc),
                )
                yield _emit("run_failed", ReplayRunState.model_validate(failed).model_dump(mode="json"))

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app
