from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import Connection

from replay_service.errors import NotFoundError


class ReplayRepository:
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
                    storage_root_prefix,
                    started_at_utc,
                    ended_at_utc,
                    timezone
                FROM ingest.raw_sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise NotFoundError(
                code="replay_session_not_found",
                message="Raw session was not found",
                details={"session_id": session_id},
            )

        return row

    def list_segments(self, session_id: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    segment_id,
                    name,
                    order_index,
                    started_at_utc,
                    ended_at_utc,
                    planned,
                    notes
                FROM ingest.session_segments
                WHERE session_id = %s
                ORDER BY order_index ASC
                """,
                (session_id,),
            )
            return cur.fetchall()

    def list_streams_for_manifest(self, session_id: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.stream_id,
                    s.device_id,
                    s.stream_name,
                    s.stream_kind,
                    s.sample_count,
                    s.started_at_utc,
                    s.ended_at_utc,
                    s.file_ref,
                    s.checksum_sha256,
                    samples.object_key AS sample_object_key,
                    samples.content_type AS sample_content_type,
                    samples.upload_status AS sample_upload_status,
                    metadata.artifact_path AS metadata_artifact_path,
                    metadata.object_key AS metadata_object_key
                FROM ingest.session_streams AS s
                LEFT JOIN ingest.ingest_artifacts AS samples
                    ON samples.session_id = s.session_id
                    AND samples.artifact_path = s.file_ref
                LEFT JOIN ingest.ingest_artifacts AS metadata
                    ON metadata.session_id = s.session_id
                    AND metadata.stream_name = s.stream_name
                    AND metadata.artifact_role = 'stream_metadata'
                WHERE s.session_id = %s
                ORDER BY s.stream_name ASC
                """,
                (session_id,),
            )
            return cur.fetchall()

    def list_events_between(
        self,
        session_id: str,
        started_at_utc: datetime,
        ended_at_utc: datetime,
    ) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    event_id,
                    event_type,
                    occurred_at_utc,
                    source,
                    payload
                FROM ingest.session_events
                WHERE session_id = %s
                  AND occurred_at_utc >= %s
                  AND occurred_at_utc <= %s
                ORDER BY occurred_at_utc ASC, event_id ASC
                """,
                (session_id, started_at_utc, ended_at_utc),
            )
            return cur.fetchall()
