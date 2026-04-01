from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from personalization_worker.models import AdaptationState, ProfileCreate, ProfileResponse


class InMemoryProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}

    def get(self, subject_id: str) -> Optional[ProfileResponse]:
        raw = self._profiles.get(subject_id)
        if raw is None:
            return None
        return ProfileResponse(
            subject_id=raw["subject_id"],
            physiology_baseline=raw["physiology_baseline"],
            adaptation_state=raw["adaptation_state"],
            created_at_utc=raw["created_at_utc"],
            updated_at_utc=raw["updated_at_utc"],
            notes=raw.get("notes"),
        )

    def put(self, payload: ProfileCreate) -> ProfileResponse:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        existing = self._profiles.get(payload.subject_id)
        created = now if existing is None else existing["created_at_utc"]
        raw = {
            "subject_id": payload.subject_id,
            "physiology_baseline": payload.physiology_baseline,
            "adaptation_state": payload.adaptation_state.model_dump(),
            "created_at_utc": created,
            "updated_at_utc": now,
            "notes": payload.notes,
        }
        self._profiles[payload.subject_id] = raw
        return ProfileResponse(
            subject_id=raw["subject_id"],
            physiology_baseline=raw["physiology_baseline"],
            adaptation_state=AdaptationState(**raw["adaptation_state"]),
            created_at_utc=raw["created_at_utc"],
            updated_at_utc=raw["updated_at_utc"],
            notes=raw.get("notes"),
        )

    def delete(self, subject_id: str) -> bool:
        if subject_id in self._profiles:
            del self._profiles[subject_id]
            return True
        return False
