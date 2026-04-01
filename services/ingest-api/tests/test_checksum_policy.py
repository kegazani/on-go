from __future__ import annotations

from ingest_api.models import FinalizeRawSessionRequest
from ingest_api.service import IngestService


def test_finalize_request_accepts_only_canonical_checksum_path() -> None:
    model = FinalizeRawSessionRequest.model_validate(
        {
            "package_checksum_sha256": "a" * 64,
            "checksum_file_path": "checksums/SHA256SUMS",
        }
    )
    assert model.checksum_file_path == "checksums/SHA256SUMS"


def test_finalize_request_rejects_non_canonical_checksum_path() -> None:
    try:
        FinalizeRawSessionRequest.model_validate(
            {
                "package_checksum_sha256": "a" * 64,
                "checksum_file_path": "checksums/other.txt",
            }
        )
    except Exception as exc:  # pydantic validation error
        assert "checksums/SHA256SUMS" in str(exc)
        return

    raise AssertionError("Validation should fail for non-canonical checksum path")


def test_parse_sha256sums_accepts_valid_lines() -> None:
    entries = IngestService._parse_sha256sums(
        b"a" * 64 + b" manifest/session.json\n" + b"b" * 64 + b" streams/watch_heart_rate/samples.csv\n"
    )
    assert entries["manifest/session.json"] == "a" * 64
    assert entries["streams/watch_heart_rate/samples.csv"] == "b" * 64


def test_parse_sha256sums_rejects_duplicate_paths() -> None:
    try:
        IngestService._parse_sha256sums(
            b"a" * 64 + b" manifest/session.json\n" + b"b" * 64 + b" manifest/session.json\n"
        )
    except Exception as exc:
        assert "duplicate" in str(exc).lower()
        return

    raise AssertionError("Validation should fail for duplicate checksum paths")


def test_validate_checksum_policy_detects_mismatch() -> None:
    artifacts = [
        {
            "artifact_path": "manifest/session.json",
            "checksum_sha256": "a" * 64,
        },
        {
            "artifact_path": "streams/watch_heart_rate/samples.csv",
            "checksum_sha256": "b" * 64,
        },
        {
            "artifact_path": "checksums/SHA256SUMS",
            "checksum_sha256": "c" * 64,
        },
    ]
    checksum_entries = {
        "manifest/session.json": "a" * 64,
        "streams/watch_heart_rate/samples.csv": "d" * 64,
    }

    errors = IngestService._validate_checksum_policy(
        checksum_entries=checksum_entries,
        artifacts=artifacts,
        checksum_file_path="checksums/SHA256SUMS",
        package_checksum_sha256="c" * 64,
    )
    assert "checksum_manifest_hash_mismatch" in errors
