from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from replay_service.config import Settings
from replay_service.db import Database
from replay_service.errors import ApiError
from replay_service.models import (
    ErrorResponse,
    ReplayManifestResponse,
    ReplayWindowRequest,
    ReplayWindowResponse,
)
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

    return app
