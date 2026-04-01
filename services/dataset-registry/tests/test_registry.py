from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dataset_registry.models import DatasetRecord
from dataset_registry.registry import DatasetRegistry


def _record(version: str) -> DatasetRecord:
    return DatasetRecord(
        dataset_id="wesad",
        dataset_version=version,
        source="WESAD",
        source_uri="https://example.org/wesad",
        source_license="research-only",
        ingestion_script_version="wesad-import-v1",
        preprocessing_version="e2-v1",
        split_strategy="subject-wise",
        target_tracks=["activity/context", "arousal"],
        labels_available=["activity_label", "arousal_score"],
        modalities_available=["ecg"],
        row_count=3,
        subject_count=3,
        session_count=3,
        created_at_utc=datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc),
        metadata_object=f"datasets/wesad/{version}/manifest/dataset-metadata.json",
    )


def test_registry_upsert_replaces_same_dataset_version(tmp_path: Path) -> None:
    registry = DatasetRegistry(tmp_path / "datasets.jsonl")

    registry.upsert(_record("wesad-v1"))
    updated = _record("wesad-v1")
    updated.subject_count = 10
    registry.upsert(updated)

    records = registry.list_records()
    assert len(records) == 1
    assert records[0].subject_count == 10


def test_registry_upsert_keeps_distinct_versions(tmp_path: Path) -> None:
    registry = DatasetRegistry(tmp_path / "datasets.jsonl")
    registry.upsert(_record("wesad-v1"))
    registry.upsert(_record("wesad-v2"))

    records = registry.list_records()
    assert len(records) == 2
    assert {item.dataset_version for item in records} == {"wesad-v1", "wesad-v2"}
