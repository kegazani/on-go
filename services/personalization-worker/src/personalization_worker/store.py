from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

import psycopg

from personalization_worker.models import AdaptationState, ProfileCreate, ProfileResponse


def _utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ProfileStore(Protocol):
    def get(self, subject_id: str) -> Optional[ProfileResponse]: ...

    def put(self, payload: ProfileCreate) -> ProfileResponse: ...

    def ping(self) -> None: ...


class InMemoryProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}

    def ping(self) -> None:
        return None

    def get(self, subject_id: str) -> Optional[ProfileResponse]:
        raw = self._profiles.get(subject_id)
        if raw is None:
            return None
        return ProfileResponse(
            subject_id=raw["subject_id"],
            physiology_baseline=raw["physiology_baseline"],
            adaptation_state=AdaptationState(**raw["adaptation_state"]),
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


class PostgresProfileStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def ping(self) -> None:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")

    def get(self, subject_id: str) -> Optional[ProfileResponse]:
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT subject_id, physiology_baseline, adaptation_state, notes,
                           created_at_utc, updated_at_utc
                    FROM personalization.user_profiles
                    WHERE subject_id = %s
                    """,
                    (subject_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        sid, physio, adapt, notes, created, updated = row
        adapt_dict = adapt if isinstance(adapt, dict) else json.loads(adapt)
        physio_dict = physio if isinstance(physio, dict) else json.loads(physio)
        return ProfileResponse(
            subject_id=sid,
            physiology_baseline=physio_dict,
            adaptation_state=AdaptationState(**adapt_dict),
            created_at_utc=_utc_z(created) if isinstance(created, datetime) else str(created),
            updated_at_utc=_utc_z(updated) if isinstance(updated, datetime) else str(updated),
            notes=notes,
        )

    def put(self, payload: ProfileCreate) -> ProfileResponse:
        physio_json = json.dumps(payload.physiology_baseline)
        adapt_json = json.dumps(payload.adaptation_state.model_dump())
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO personalization.user_profiles (
                        subject_id, physiology_baseline, adaptation_state, notes,
                        created_at_utc, updated_at_utc
                    )
                    VALUES (
                        %s, %s::jsonb, %s::jsonb, %s, NOW(), NOW()
                    )
                    ON CONFLICT (subject_id) DO UPDATE SET
                        physiology_baseline = EXCLUDED.physiology_baseline,
                        adaptation_state = EXCLUDED.adaptation_state,
                        notes = EXCLUDED.notes,
                        updated_at_utc = NOW()
                    RETURNING created_at_utc, updated_at_utc
                    """,
                    (payload.subject_id, physio_json, adapt_json, payload.notes),
                )
                created, updated = cur.fetchone()
        return ProfileResponse(
            subject_id=payload.subject_id,
            physiology_baseline=payload.physiology_baseline,
            adaptation_state=payload.adaptation_state,
            created_at_utc=_utc_z(created) if isinstance(created, datetime) else str(created),
            updated_at_utc=_utc_z(updated) if isinstance(updated, datetime) else str(updated),
            notes=payload.notes,
        )
