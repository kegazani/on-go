from __future__ import annotations

import csv
import hashlib
import json
import pickle
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dataset_registry.models import (
    DatasetRecord,
    SplitManifest,
    UnifiedSegmentLabel,
    UnifiedSession,
    UnifiedSubject,
)


@dataclass
class GenericImportResult:
    record: DatasetRecord
    subjects: list[UnifiedSubject]
    sessions: list[UnifiedSession]
    segment_labels: list[UnifiedSegmentLabel]
    split_manifest: SplitManifest
    warnings: list[str]


GREX_GENRE_ACTIVITY = {
    "Horror": ("stimulus_horror", "stimulus"),
    "Comedy": ("stimulus_comedy", "stimulus"),
    "Drama": ("stimulus_drama", "stimulus"),
    "Action": ("stimulus_action", "stimulus"),
    "Romance": ("stimulus_romance", "stimulus"),
    "Documentary": ("stimulus_documentary", "stimulus"),
}

EMOWEAR_CONDITION_MAP = {
    "front": ("phone_front_carry", "mobility"),
    "back": ("phone_back_carry", "mobility"),
    "water": ("water_exposure_task", "exposure"),
}


def import_grex_dataset(
    source_dir: Path,
    output_dir: Path,
    dataset_version: str,
    preprocessing_version: str,
    source_uri: Optional[str],
    source_license: Optional[str],
) -> GenericImportResult:
    dataset_id = "grex"
    annotation = _load_pickle(source_dir / "4_Annotation" / "Transformed" / "ann_trans_data_segments.pickle")
    questionnaire = _load_pickle(source_dir / "2_Questionnaire" / "Transformed" / "quest_trans_data_segments.pickle")
    stimulus = _load_pickle(source_dir / "1_Stimuli" / "Transformed" / "stimu_trans_data_segments.pickle")

    ar = annotation.get("ar_seg", [])
    vl = annotation.get("vl_seg", [])
    unc = annotation.get("unc_seg", [])
    ts = annotation.get("ts_seg", [])
    ids = questionnaire.get("ID", [])
    genres = stimulus.get("genre", [])
    sessions_raw = stimulus.get("session", [])

    n = min(len(ar), len(vl), len(unc), len(ts), len(ids), len(genres), len(sessions_raw))
    if n == 0:
        raise ValueError("G-REx transformed segment artifacts are empty or inconsistent")

    subjects_map: dict[str, UnifiedSubject] = {}
    sessions_map: dict[str, UnifiedSession] = {}
    labels: list[UnifiedSegmentLabel] = []
    warnings: list[str] = []

    for idx in range(n):
        raw_id = int(ids[idx])
        subject_code = f"S{raw_id:03d}"
        subject_id = f"{dataset_id}:{subject_code}"
        session_num = int(sessions_raw[idx])
        session_id = f"{dataset_id}:{dataset_version}:{subject_code}:session_{session_num:03d}"

        if subject_id not in subjects_map:
            subjects_map[subject_id] = UnifiedSubject(
                subject_id=subject_id,
                source_subject_id=subject_code,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
            )
        if session_id not in sessions_map:
            sessions_map[session_id] = UnifiedSession(
                session_id=session_id,
                subject_id=subject_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
            )

        arousal_score = _scale_1_5_to_1_9(ar[idx])
        valence_score = _scale_1_5_to_1_9(vl[idx])
        genre = str(genres[idx])
        activity_label, activity_group = GREX_GENRE_ACTIVITY.get(genre, ("stimulus_other", "stimulus"))
        if genre not in GREX_GENRE_ACTIVITY:
            warnings.append(f"unmapped genre '{genre}' mapped to stimulus_other")

        confidence = _grex_confidence_from_uncertainty(unc[idx])
        sample_count = _safe_positive_int(ts[idx])

        labels.append(
            UnifiedSegmentLabel(
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                session_id=session_id,
                segment_id=f"{session_id}:segment_{idx + 1:05d}",
                source_label="grex_arousal_1to5",
                source_label_value=str(ar[idx]),
                activity_label=activity_label,
                activity_group=activity_group,
                arousal_score=arousal_score,
                valence_score=valence_score,
                confidence=confidence,
                source_segment_start_index=None,
                source_segment_end_index=None,
                source_sample_count=sample_count,
                source="dataset_mapping",
            )
        )

    subjects = sorted(subjects_map.values(), key=lambda item: item.subject_id)
    sessions = sorted(sessions_map.values(), key=lambda item: item.session_id)
    split_manifest = _build_subjectwise_split(dataset_id=dataset_id, dataset_version=dataset_version, subjects=subjects)

    record = DatasetRecord(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        source="G-REx",
        source_uri=source_uri,
        source_license=source_license,
        ingestion_script_version="grex-import-v1",
        preprocessing_version=preprocessing_version,
        split_strategy="subject-wise",
        target_tracks=["activity/context", "arousal", "valence_exploratory"],
        labels_available=["genre", "arousal_1to5", "valence_1to5", "activity_label", "arousal_score", "valence_score"],
        modalities_available=["eda", "ppg"],
        row_count=len(labels),
        subject_count=len(subjects),
        session_count=len(sessions),
        created_at_utc=datetime.now(timezone.utc),
        metadata_object=f"{dataset_id}/{dataset_version}/manifest/dataset-metadata.json",
    )

    _write_artifacts(output_dir=output_dir, record=record, subjects=subjects, sessions=sessions, labels=labels, split_manifest=split_manifest)
    return GenericImportResult(record=record, subjects=subjects, sessions=sessions, segment_labels=labels, split_manifest=split_manifest, warnings=sorted(set(warnings)))


def import_emowear_dataset(
    source_dir: Path,
    output_dir: Path,
    dataset_version: str,
    preprocessing_version: str,
    source_uri: Optional[str],
    source_license: Optional[str],
) -> GenericImportResult:
    dataset_id = "emowear"
    participant_dirs = sorted(path for path in source_dir.iterdir() if path.is_dir() and "-" in path.name)
    if not participant_dirs:
        raise ValueError(f"No participant directories found under {source_dir}")

    subjects: list[UnifiedSubject] = []
    sessions: list[UnifiedSession] = []
    labels: list[UnifiedSegmentLabel] = []
    warnings: list[str] = []

    for participant in participant_dirs:
        source_subject_id = participant.name
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

        segment_index = 0
        for condition, (activity_label, activity_group) in EMOWEAR_CONDITION_MAP.items():
            zip_path = participant / f"{condition}.zip"
            if not zip_path.exists():
                continue
            segment_index += 1
            sample_count = _emowear_sample_count(zip_path)
            if sample_count is None:
                warnings.append(f"{source_subject_id}:{condition} missing parseable output csv")
            arousal_score, valence_score = _emowear_proxy_scores(condition)
            labels.append(
                UnifiedSegmentLabel(
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    session_id=session_id,
                    segment_id=f"{session_id}:segment_{segment_index:03d}",
                    source_label="emowear_condition",
                    source_label_value=condition,
                    activity_label=activity_label,
                    activity_group=activity_group,
                    arousal_score=arousal_score,
                    valence_score=valence_score,
                    confidence=0.72,
                    source_segment_start_index=None,
                    source_segment_end_index=None,
                    source_sample_count=sample_count,
                    source="proxy_mapping",
                )
            )

        if segment_index == 0:
            warnings.append(f"{source_subject_id}: no front/back/water files found")

    split_manifest = _build_subjectwise_split(dataset_id=dataset_id, dataset_version=dataset_version, subjects=subjects)
    record = DatasetRecord(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        source="EmoWear",
        source_uri=source_uri,
        source_license=source_license,
        ingestion_script_version="emowear-import-v1-proxy",
        preprocessing_version=preprocessing_version,
        split_strategy="subject-wise",
        target_tracks=["activity/context", "arousal_proxy", "valence_proxy"],
        labels_available=["emowear_condition", "activity_label", "arousal_score_proxy", "valence_score_proxy"],
        modalities_available=["bh3_ecg", "bh3_breathing", "e4_acc", "e4_bvp", "e4_eda", "e4_temp"],
        row_count=len(labels),
        subject_count=len(subjects),
        session_count=len(sessions),
        created_at_utc=datetime.now(timezone.utc),
        metadata_object=f"{dataset_id}/{dataset_version}/manifest/dataset-metadata.json",
    )

    _write_artifacts(output_dir=output_dir, record=record, subjects=subjects, sessions=sessions, labels=labels, split_manifest=split_manifest)
    return GenericImportResult(record=record, subjects=subjects, sessions=sessions, segment_labels=labels, split_manifest=split_manifest, warnings=warnings)


def import_dapper_dataset(
    source_dir: Path,
    output_dir: Path,
    dataset_version: str,
    preprocessing_version: str,
    source_uri: Optional[str],
    source_license: Optional[str],
) -> GenericImportResult:
    dataset_id = "dapper"
    participant_dirs = sorted(path for path in source_dir.iterdir() if path.is_dir() and path.name.isdigit())
    if not participant_dirs:
        raise ValueError(f"No participant directories found under {source_dir}")

    subjects: list[UnifiedSubject] = []
    sessions: list[UnifiedSession] = []
    labels: list[UnifiedSegmentLabel] = []
    warnings: list[str] = []

    for participant_dir in participant_dirs:
        source_subject_id = participant_dir.name
        subject_id = f"{dataset_id}:{source_subject_id}"
        subjects.append(
            UnifiedSubject(
                subject_id=subject_id,
                source_subject_id=source_subject_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
            )
        )

        stratum = _dapper_subject_stratum(source_subject_id)
        activity_label, activity_group, arousal_score = _dapper_proxy_mapping(stratum)
        base_files = sorted(
            path
            for path in participant_dir.glob("*.csv")
            if not path.name.endswith("_ACC.csv")
            and not path.name.endswith("_GSR.csv")
            and not path.name.endswith("_PPG.csv")
        )
        if not base_files:
            warnings.append(f"{source_subject_id}: no base csv sessions found")
            continue

        for session_index, base_file in enumerate(base_files, start=1):
            session_id = f"{dataset_id}:{dataset_version}:{source_subject_id}:session_{session_index:03d}"
            sessions.append(
                UnifiedSession(
                    session_id=session_id,
                    subject_id=subject_id,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                )
            )
            sample_count = _csv_data_row_count(base_file)
            labels.append(
                UnifiedSegmentLabel(
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    session_id=session_id,
                    segment_id=f"{session_id}:segment_001",
                    source_label="dapper_subject_stratum",
                    source_label_value=str(stratum),
                    activity_label=activity_label,
                    activity_group=activity_group,
                    arousal_score=arousal_score,
                    valence_score=5,
                    confidence=0.55,
                    source_segment_start_index=0,
                    source_segment_end_index=(sample_count - 1) if sample_count else None,
                    source_sample_count=sample_count,
                    source="proxy_mapping",
                )
            )

    split_manifest = _build_subjectwise_split(dataset_id=dataset_id, dataset_version=dataset_version, subjects=subjects)
    record = DatasetRecord(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        source="DAPPER",
        source_uri=source_uri,
        source_license=source_license,
        ingestion_script_version="dapper-import-v1-proxy",
        preprocessing_version=preprocessing_version,
        split_strategy="subject-wise",
        target_tracks=["activity/context_proxy", "arousal_proxy"],
        labels_available=["dapper_subject_stratum", "activity_label_proxy", "arousal_score_proxy"],
        modalities_available=["heart_rate", "motion", "gsr", "acc", "ppg"],
        row_count=len(labels),
        subject_count=len(subjects),
        session_count=len(sessions),
        created_at_utc=datetime.now(timezone.utc),
        metadata_object=f"{dataset_id}/{dataset_version}/manifest/dataset-metadata.json",
    )

    _write_artifacts(output_dir=output_dir, record=record, subjects=subjects, sessions=sessions, labels=labels, split_manifest=split_manifest)
    return GenericImportResult(record=record, subjects=subjects, sessions=sessions, segment_labels=labels, split_manifest=split_manifest, warnings=warnings)


def _write_artifacts(
    output_dir: Path,
    record: DatasetRecord,
    subjects: list[UnifiedSubject],
    sessions: list[UnifiedSession],
    labels: list[UnifiedSegmentLabel],
    split_manifest: SplitManifest,
) -> None:
    dataset_root = output_dir / record.dataset_id / record.dataset_version
    unified_root = dataset_root / "unified"
    manifest_root = dataset_root / "manifest"
    unified_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    _write_jsonl(unified_root / "subjects.jsonl", [item.model_dump(mode="json") for item in subjects])
    _write_jsonl(unified_root / "sessions.jsonl", [item.model_dump(mode="json") for item in sessions])
    _write_jsonl(unified_root / "segment-labels.jsonl", [item.model_dump(mode="json") for item in labels])
    (manifest_root / "split-manifest.json").write_text(
        json.dumps(split_manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (manifest_root / "dataset-metadata.json").write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_pickle(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected dict payload in {path}")
    return payload


def _scale_1_5_to_1_9(value: object) -> int:
    numeric = float(value)
    clipped = min(max(int(round(numeric)), 1), 5)
    return int((clipped - 1) * 2 + 1)


def _grex_confidence_from_uncertainty(value: object) -> float:
    if value is None:
        return 0.95
    try:
        numeric = float(value)
    except Exception:
        return 0.75
    numeric = min(max(numeric, 1.0), 5.0)
    confidence = 1.0 - ((numeric - 1.0) / 4.0) * 0.45
    return round(confidence, 4)


def _safe_positive_int(value: object) -> int | None:
    try:
        numeric = int(float(value))
    except Exception:
        return None
    if numeric <= 0:
        return None
    return numeric


def _emowear_sample_count(zip_path: Path) -> int | None:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            output_names = [name for name in archive.namelist() if name.startswith("output_") and name.endswith(".csv")]
            if not output_names:
                return None
            content = archive.read(output_names[0]).decode("utf-8", errors="replace").splitlines()
            return max(len(content) - 1, 0)
    except Exception:
        return None


def _emowear_proxy_scores(condition: str) -> tuple[int, int]:
    if condition == "water":
        return (7, 3)
    if condition == "back":
        return (5, 5)
    return (4, 6)


def _dapper_subject_stratum(subject_id: str) -> int:
    if not subject_id:
        return 0
    return int(subject_id[0])


def _dapper_proxy_mapping(stratum: int) -> tuple[str, str, int]:
    if stratum <= 1:
        return ("proxy_stratum_one", "proxy_stratum", 3)
    if stratum == 2:
        return ("proxy_stratum_two", "proxy_stratum", 5)
    return ("proxy_stratum_three", "proxy_stratum", 7)


def _csv_data_row_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            count = sum(1 for _ in reader)
        return max(count, 0)
    except Exception:
        return None
