from __future__ import annotations

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from ingest_api.config import Settings
from ingest_api.db import Database
from ingest_api.errors import ApiError
from ingest_api.models import (
    CompleteArtifactsRequest,
    CompleteArtifactsResponse,
    CreateRawSessionIngestRequest,
    CreateRawSessionIngestResponse,
    ErrorResponse,
    FinalizeRawSessionRequest,
    FinalizeRawSessionResponse,
    PresignArtifactsRequest,
    PresignArtifactsResponse,
    RawSessionIngestState,
)
from ingest_api.service import IngestService
from ingest_api.storage import S3Storage


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    database = Database(cfg.database_dsn)
    storage = S3Storage(cfg)
    service = IngestService(database=database, storage=storage)

    app = FastAPI(
        title="On-Go Raw Session Ingest API",
        version="0.1.0",
        description="Runtime ingest lifecycle for raw sessions: Postgres metadata + MinIO/S3 artifacts.",
    )

    @app.on_event("startup")
    def on_startup() -> None:
        storage.ensure_bucket()

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        response = ErrorResponse(error={"code": exc.code, "message": exc.message, "details": exc.details})
        return JSONResponse(status_code=exc.status_code, content=response.model_dump(mode="json"))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/raw-sessions", response_model=CreateRawSessionIngestResponse, status_code=201)
    async def create_raw_session_ingest(
        payload: CreateRawSessionIngestRequest,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> CreateRawSessionIngestResponse:
        raw_body = await request.body()
        return service.create_raw_session(
            request=payload,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )

    @app.get("/v1/raw-sessions/{session_id}", response_model=RawSessionIngestState)
    async def get_raw_session_ingest_state(session_id: str) -> RawSessionIngestState:
        return service.get_raw_session_state(session_id)

    @app.post(
        "/v1/raw-sessions/{session_id}/artifacts/presign",
        response_model=PresignArtifactsResponse,
    )
    async def presign_artifacts(
        session_id: str,
        payload: PresignArtifactsRequest,
    ) -> PresignArtifactsResponse:
        return service.presign_artifacts(session_id=session_id, request=payload)

    @app.post(
        "/v1/raw-sessions/{session_id}/artifacts/complete",
        response_model=CompleteArtifactsResponse,
    )
    async def complete_artifacts_batch(
        session_id: str,
        payload: CompleteArtifactsRequest,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> CompleteArtifactsResponse:
        raw_body = await request.body()
        return service.complete_artifacts(
            session_id=session_id,
            request=payload,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )

    @app.post(
        "/v1/raw-sessions/{session_id}/finalize",
        response_model=FinalizeRawSessionResponse,
    )
    async def finalize_raw_session_ingest(
        session_id: str,
        payload: FinalizeRawSessionRequest,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> FinalizeRawSessionResponse:
        raw_body = await request.body()
        return service.finalize_session(
            session_id=session_id,
            request=payload,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
        )

    return app
