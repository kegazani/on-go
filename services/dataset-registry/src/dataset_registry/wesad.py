from __future__ import annotations

import csv
import hashlib
import json
import pickle
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Optional

from dataset_registry.models import (
    DatasetRecord,
    SplitManifest,
    UnifiedSegmentLabel,
    UnifiedSession,
    UnifiedSubject,
)

WESAD_SUBJECT_RE = re.compile(r"^S\d+$")

# Official WESAD labels are typically encoded as:
# 1 baseline, 2 stress, 3 amusement, 4 meditation.
WESAD_LABEL_MAPPING: dict[int, dict[str, object]] = {
    1: {
        "activity_label": "seated_rest",
        "activity_group": "rest",
        "arousal_score": 2,
        "valence_score": 5,
    },
    2: {
        "activity_label": "focused_cognitive_task",
        "activity_group": "cognitive",
        "arousal_score": 8,
        "valence_score": 3,
    },
    3: {
        "activity_label": "focused_cognitive_task",
        "activity_group": "cognitive",
        "arousal_score": 6,
        "valence_score": 8,
    },
    4: {
        "activity_label": "recovery_rest",
        "activity_group": "recovery",
        "arousal_score": 2,
        "valence_score": 7,
    },
}


@dataclass
class WESADImportResult:
    record: DatasetRecord
    subjects: list[UnifiedSubject]
    sessions: list[UnifiedSession]
    segment_labels: list[UnifiedSegmentLabel]
    split_manifest: SplitManifest
    warnings: list[str]


def import_wesad_dataset(
    source_dir: Path,
    output_dir: Path,
    dataset_version: str,
    preprocessing_version: str,
    source_uri: Optional[str],
    source_license: Optional[str],
) -> WESADImportResult:
    subject_dirs = sorted(path for path in source_dir.iterdir() if path.is_dir() and WESAD_SUBJECT_RE.match(path.name))
    if not subject_dirs:
        raise ValueError(f"No subject directories S* found under {source_dir}")

    dataset_id = "wesad"
    subjects: list[UnifiedSubject] = []
    sessions: list[UnifiedSession] = []
    labels: list[UnifiedSegmentLabel] = []
    warnings: list[str] = []

    for subject_dir in subject_dirs:
        source_subject_id = subject_dir.name
        subject_id = f"{dataset_id}:{source_subject_id}"
        session_id = f"{dataset_id}:{dataset_version}:{source_subject_id}:session_001"

        subjects.append(
            UnifiedSubject(
                subject_id=subject_id,
                source_subject_id=source_subject_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
            )
        )
        sessions.append(
            UnifiedSession(
                session_id=session_id,
                subject_id=subject_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
            )
        )

        label_sequence = _load_wesad_label_sequence(subject_dir)
        if not label_sequence:
            warnings.append(f"{source_subject_id}: no parseable labels found, subject skipped for segment labels")
            continue

        contiguous_segments = list(_iter_labeled_segments(label_sequence))
        if not contiguous_segments:
            warnings.append(f"{source_subject_id}: only unlabeled/zero-state samples found, subject skipped")
            continue

        unmapped_source_values: set[int] = set()
        for segment_index, (source_label_value, start_index, end_index) in enumerate(contiguous_segments, start=1):
            mapped = WESAD_LABEL_MAPPING.get(source_label_value)
            confidence = 0.8
            if mapped is None:
                unmapped_source_values.add(source_label_value)
                mapped = {
                    "activity_label": "unknown",
                    "activity_group": "unknown",
                    "arousal_score": 5,
                    "valence_score": 5,
                }
                confidence = 0.3

            labels.append(
                UnifiedSegmentLabel(
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    session_id=session_id,
                    segment_id=f"{session_id}:segment_{segment_index:03d}",
                    source_label="wesad_state",
                    source_label_value=str(source_label_value),
                    activity_label=str(mapped["activity_label"]),
                    activity_group=str(mapped["activity_group"]),
                    arousal_score=int(mapped["arousal_score"]),
                    valence_score=int(mapped["valence_score"]),
                    confidence=confidence,
                    source_segment_start_index=start_index,
                    source_segment_end_index=end_index,
                    source_sample_count=(end_index - start_index + 1),
                    source="dataset_mapping",
                )
            )

        if unmapped_source_values:
            warnings.append(
                f"{source_subject_id}: unmapped source labels {sorted(unmapped_source_values)} preserved as unknown segments"
            )

    split_manifest = _build_subjectwise_split(dataset_id=dataset_id, dataset_version=dataset_version, subjects=subjects)

    dataset_root = output_dir / dataset_id / dataset_version
    unified_root = dataset_root / "unified"
    manifest_root = dataset_root / "manifest"
    unified_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    _write_jsonl(unified_root / "subjects.jsonl", [item.model_dump(mode="json") for item in subjects])
    _write_jsonl(unified_root / "sessions.jsonl", [item.model_dump(mode="json") for item in sessions])
    _write_jsonl(unified_root / "segment-labels.jsonl", [item.model_dump(mode="json") for item in labels])

    split_payload = split_manifest.model_dump(mode="json")
    (manifest_root / "split-manifest.json").write_text(
        json.dumps(split_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    record = DatasetRecord(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        source="WESAD",
        source_uri=source_uri,
        source_license=source_license,
        ingestion_script_version="wesad-import-v2",
        preprocessing_version=preprocessing_version,
        split_strategy="subject-wise",
        target_tracks=["activity/context", "arousal", "valence_exploratory"],
        labels_available=["wesad_state", "activity_label", "arousal_score", "valence_score"],
        modalities_available=["chest_ecg", "chest_acc", "eda", "temp", "resp"],
        row_count=len(labels),
        subject_count=len(subjects),
        session_count=len(sessions),
        created_at_utc=datetime.now(timezone.utc),
        metadata_object=str((manifest_root / "dataset-metadata.json").relative_to(output_dir)),
    )

    (manifest_root / "dataset-metadata.json").write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return WESADImportResult(
        record=record,
        subjects=subjects,
        sessions=sessions,
        segment_labels=labels,
        split_manifest=split_manifest,
        warnings=warnings,
    )


def _build_subjectwise_split(
    dataset_id: str,
    dataset_version: str,
    subjects: list[UnifiedSubject],
) -> SplitManifest:
    train: list[str] = []
    validation: list[str] = []
    test: list[str] = []

    for subject in subjects:
        bucket = int(hashlib.sha1(subject.subject_id.encode("utf-8")).hexdigest()[:2], 16)
        score = bucket / 255.0
        if score < 0.7:
            train.append(subject.subject_id)
        elif score < 0.85:
            validation.append(subject.subject_id)
        else:
            test.append(subject.subject_id)

    # Keep non-empty splits for tiny local subsets.
    if not validation and len(train) >= 2:
        validation.append(train.pop())
    if not test and len(train) >= 2:
        test.append(train.pop())

    return SplitManifest(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        strategy="subject-wise",
        train_subject_ids=sorted(train),
        validation_subject_ids=sorted(validation),
        test_subject_ids=sorted(test),
    )


def _load_wesad_label_sequence(subject_dir: Path) -> list[int]:
    csv_candidates = [
        subject_dir / "label.csv",
        subject_dir / "labels.csv",
        subject_dir / f"{subject_dir.name}_labels.csv",
    ]
    for candidate in csv_candidates:
        if candidate.exists():
            labels = _load_label_csv(candidate)
            if labels:
                return labels

    pickle_candidates = [
        subject_dir / f"{subject_dir.name}.pkl",
        subject_dir / "data.pkl",
    ]
    for candidate in pickle_candidates:
        if candidate.exists():
            labels = _load_label_pickle(candidate)
            if labels:
                return labels

    return []


def _load_label_csv(path: Path) -> list[int]:
    labels: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            value = row[0].strip()
            if not value:
                continue
            try:
                labels.append(int(float(value)))
            except ValueError:
                continue

    return labels


def _load_label_pickle(path: Path) -> list[int]:
    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle, encoding="latin1")
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []

    label_obj = payload.get("label")
    if label_obj is None:
        return []

    # Supports plain lists and numpy-like arrays.
    try:
        iterable = list(label_obj)
    except Exception:
        return []

    labels: list[int] = []
    for item in iterable:
        try:
            labels.append(int(float(item)))
        except Exception:
            continue
    return labels


def _iter_labeled_segments(labels: list[int]) -> list[tuple[int, int, int]]:
    segments: list[tuple[int, int, int]] = []
    cursor = 0
    for value, group in groupby(labels):
        run_length = sum(1 for _ in group)
        start_index = cursor
        end_index = cursor + run_length - 1
        if value > 0:
            segments.append((value, start_index, end_index))
        cursor += run_length
    return segments


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
