from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import Connection
from psycopg.types.json import Json

from signal_processing_worker.errors import NotFoundError


class ProcessingRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    session_id,
                    subject_id,
                    ingest_status,
                    started_at_utc,
                    ended_at_utc,
                    timezone,
                    storage_root_prefix
                FROM ingest.raw_sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise NotFoundError(
                code="processing_session_not_found",
                message="Raw session was not found",
                details={"session_id": session_id},
            )

        return row

    def list_streams_for_processing(self, session_id: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.stream_id,
                    s.device_id,
                    s.stream_name,
                    s.stream_kind,
                    s.sample_count,
                    s.file_ref,
                    s.missing_intervals,
                    samples.object_key AS sample_object_key,
                    samples.upload_status AS sample_upload_status
                FROM ingest.session_streams AS s
                LEFT JOIN ingest.ingest_artifacts AS samples
                    ON samples.session_id = s.session_id
                    AND samples.artifact_path = s.file_ref
                WHERE s.session_id = %s
                ORDER BY s.stream_name ASC
                """,
                (session_id,),
            )
            return cur.fetchall()

    def upsert_quality_report(
        self,
        session_id: str,
        quality_report_id: str,
        generated_at_utc: datetime,
        overall_status: str,
        checks: list[dict[str, Any]],
        notes: str | None,
        metadata: dict[str, Any],
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingest.session_quality_reports (
                    session_id,
                    quality_report_id,
                    generated_at_utc,
                    overall_status,
                    checks,
                    notes,
                    metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, quality_report_id)
                DO UPDATE SET
                    generated_at_utc = EXCLUDED.generated_at_utc,
                    overall_status = EXCLUDED.overall_status,
                    checks = EXCLUDED.checks,
                    notes = EXCLUDED.notes,
                    metadata = EXCLUDED.metadata
                """,
                (
                    session_id,
                    quality_report_id,
                    generated_at_utc,
                    overall_status,
                    Json(checks),
                    notes,
                    Json(metadata),
                ),
            )
