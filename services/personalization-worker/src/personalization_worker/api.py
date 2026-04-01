from __future__ import annotations

from fastapi import FastAPI, HTTPException

from personalization_worker.config import Settings
from personalization_worker.models import ProfileCreate, ProfileResponse
from personalization_worker.store import InMemoryProfileStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = InMemoryProfileStore()
    app = FastAPI(
        title="On-Go Personalization Worker",
        version="0.1.0",
        description="Profile store, calibration and adaptation for personalized inference.",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/profile/{subject_id}", response_model=ProfileResponse)
    async def get_profile(subject_id: str) -> ProfileResponse:
        profile = store.get(subject_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="profile not found")
        return profile

    @app.put("/v1/profile", response_model=ProfileResponse)
    async def put_profile(payload: ProfileCreate) -> ProfileResponse:
        return store.put(payload)

    return app
