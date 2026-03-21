from __future__ import annotations

from ingest_api.models import CreateRawSessionIngestRequest


def _valid_payload() -> dict:
    return {
        "session": {
            "session_id": "session-001",
            "subject_id": "subject-001",
            "schema_version": "1.0.0",
            "protocol_version": "1.0.0",
            "session_type": "paired_capture",
            "status": "completed",
            "started_at_utc": "2026-03-21T10:00:00Z",
            "ended_at_utc": "2026-03-21T10:30:00Z",
            "timezone": "Europe/Moscow",
            "capture_app_version": "0.1.0",
        },
        "subject": {
            "subject_id": "subject-001",
            "consent_version": "v1",
        },
        "devices": [
            {
                "device_id": "phone-1",
                "device_role": "coordinator_phone",
                "manufacturer": "Apple",
                "model": "iPhone",
                "source_name": "ios-app",
            }
        ],
        "segments": [
            {
                "segment_id": "seg-1",
                "name": "baseline",
                "order_index": 0,
                "started_at_utc": "2026-03-21T10:00:00Z",
                "ended_at_utc": "2026-03-21T10:10:00Z",
                "planned": True,
            }
        ],
        "streams": [
            {
                "stream_id": "stream-1",
                "device_id": "phone-1",
                "stream_name": "watch_heart_rate",
                "stream_kind": "timeseries",
                "sample_count": 100,
                "file_ref": "streams/watch_heart_rate.csv",
                "checksum_sha256": "a" * 64,
            }
        ],
        "artifacts": [
            {
                "artifact_path": "streams/watch_heart_rate.csv",
                "artifact_role": "stream_samples",
                "stream_name": "watch_heart_rate",
                "content_type": "text/csv",
                "byte_size": 256,
                "checksum_sha256": "a" * 64,
            }
        ],
    }


def test_create_request_accepts_valid_payload() -> None:
    model = CreateRawSessionIngestRequest.model_validate(_valid_payload())
    assert model.session.session_id == "session-001"


def test_create_request_rejects_unknown_stream_file_ref() -> None:
    payload = _valid_payload()
    payload["streams"][0]["file_ref"] = "streams/missing.csv"

    try:
        CreateRawSessionIngestRequest.model_validate(payload)
    except Exception as exc:  # pydantic validation error
        assert "stream.file_ref not found in artifacts" in str(exc)
        return

    raise AssertionError("Validation should fail for unknown stream file_ref")
