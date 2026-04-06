from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException

from personalization_worker.config import Settings
from personalization_worker.models import (
    L2CalibrationPatchBody,
    ProfileCreate,
    ProfileResponse,
    merge_l2_calibration_patch,
)
from personalization_worker.store import InMemoryProfileStore, PostgresProfileStore, ProfileStore


def _make_store(settings: Settings) -> ProfileStore:
    if settings.database_dsn:
        return PostgresProfileStore(settings.database_dsn)
    return InMemoryProfileStore()


def create_app(settings: Settings | None = None, store: Optional[ProfileStore] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or _make_store(settings)
    app = FastAPI(
        title="On-Go Personalization Worker",
        version="0.1.0",
        description="Profile store, calibration and adaptation for personalized inference.",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        out: dict[str, str] = {
            "status": "ok",
            "store": "postgres" if isinstance(store, PostgresProfileStore) else "memory",
        }
        if isinstance(store, PostgresProfileStore):
            try:
                store.ping()
                out["db"] = "ok"
            except Exception:
                out["db"] = "error"
        else:
            out["db"] = "n/a"
        return out

    @app.get("/v1/profile/{subject_id}", response_model=ProfileResponse)
    async def get_profile(subject_id: str) -> ProfileResponse:
        profile = store.get(subject_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="profile not found")
        return profile

    @app.put("/v1/profile", response_model=ProfileResponse)
    async def put_profile(payload: ProfileCreate) -> ProfileResponse:
        return store.put(payload)

    @app.patch(
        "/v1/profile/{subject_id}/l2-calibration",
        response_model=ProfileResponse,
    )
    async def patch_l2_calibration(
        subject_id: str,
        body: L2CalibrationPatchBody,
    ) -> ProfileResponse:
        existing = store.get(subject_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="profile not found")
        merged = merge_l2_calibration_patch(existing, body)
        return store.put(merged)

    return app
