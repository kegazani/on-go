from __future__ import annotations

import csv
import gc
import json
import pickle
import re
import sqlite3
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover - local environments may vary
    np = None


@dataclass(frozen=True)
class MarkerRule:
    kind: str
    candidates: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    title: str
    download_urls: tuple[str, ...]
    access_notes: str
    expected_rules: tuple[MarkerRule, ...]


@dataclass
class ValidationResult:
    dataset_id: str
    source_dir: str
    status: str
    checks: list[dict[str, object]]
    warnings: list[str]


@dataclass
class InspectionResult:
    dataset_id: str
    source_dir: str
    status: str
    summary: dict[str, object]
    checks: list[dict[str, object]]
    warnings: list[str]


WESAD_SUBJECT_RE = re.compile(r"^S\d+$")
EMOWEAR_PARTICIPANT_RE = re.compile(r"^\d{2}-[A-Z0-9]{4}$")
GREX_PHYSIO_RAW_RE = re.compile(r"^S\d+_physio_raw_data_M\d+\.hdf5$")

WESAD_EXPECTED_CHEST_KEYS = {"ACC", "ECG", "EMG", "EDA", "Temp", "Resp"}
WESAD_EXPECTED_WRIST_KEYS = {"ACC", "BVP", "EDA", "TEMP"}
WESAD_ALLOWED_LABELS = {0, 1, 2, 3, 4, 5, 6, 7}

EMOWEAR_META_HEADER = [
    "Code",
    "ID",
    "Sequence",
    "Experiment",
    "Empatica E4",
    "Zephyr BioHarness 3",
    "Front STb",
    "Back STb",
    "Water STb",
    "Notes",
]
EMOWEAR_QUESTIONNAIRE_HEADER = [
    "Code",
    "ID",
    "Age",
    "Gender",
    "Handedness",
    "Vision",
    "Vision aid",
    "Education",
    "Alcohol consumption",
    "Coffee consumption",
    "Tea consumption",
    "Tobacco consumption",
    "Other drug/medication consumption",
    "Normal hours of sleep",
    "Hours of sleep last night",
    "Level of Alertness",
    "Physical/psychiatric syndroms",
]
EMOWEAR_REQUIRED_E4_MEMBERS = {"ACC.csv", "BVP.csv", "EDA.csv", "HR.csv", "IBI.csv", "TEMP.csv", "info.txt", "tags.csv"}
EMOWEAR_REQUIRED_BH3_SUFFIXES = {
    "_Accel.csv",
    "_BB.csv",
    "_Breathing.csv",
    "_ECG.csv",
    "_Event_Data.csv",
    "_GPS.csv",
    "_RR.csv",
    "_SessionInfo.txt",
    "_SummaryEnhanced.csv",
    "info.txt",
}

DAPPER_REQUIRED_HEADERS = {
    "base": ["heart_rate", "motion", "GSR", "battery_info", "time"],
    "acc": ["Motion_dataX", "Motion_dataY", "Motion_dataZ", "csv_time_motion"],
    "gsr": ["GSR", "csv_time_GSR"],
    "ppg": ["PPG", "csv_time_PPG"],
}

GREX_VIDEO_INFO_HEADER = [
    "",
    "movie_ID",
    "movie_name",
    "duration",
    "bit_rate",
    "fps",
    "encoding",
    "video_resolution_width",
    "video_resolution_height",
    "genre",
]
GREX_QUESTIONNAIRE_HEADER = [
    "",
    "ID",
    "movie",
    "device",
    "session",
    "age",
    "gender",
    "friends",
    "pre-viewing",
    "pos-viewing",
    "personality",
]
GREX_STIMULI_KEYS = {"genre", "movie", "session"}
GREX_QUESTIONNAIRE_KEYS = {"ID", "device"}
GREX_PHYSIO_SEQUENCE_KEYS = {
    "EDR",
    "filt_EDA",
    "filt_PPG",
    "hr",
    "hr_idx",
    "packet_number",
    "raw_EDA",
    "raw_PPG",
    "sampling_rate",
    "ts",
}
GREX_PHYSIO_AUX_KEYS = {"EDA_quality_idx", "PPG_quality_idx"}
GREX_ANNOTATION_KEYS = {"ar_seg", "ts_seg", "unc_seg", "vl_seg"}
GREX_REQUIRED_HDF5_TOKENS = ("data", "Arousal EDA", "Valence EDA", "sampling rate", "movie")
GREX_HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"

DATASET_SPECS: dict[str, DatasetSpec] = {
    "wesad": DatasetSpec(
        dataset_id="wesad",
        title="WESAD",
        download_urls=(
            "https://ubi29.informatik.uni-siegen.de/usi/data_wesad.html",
            "https://uni-siegen.sciebo.de/s/HGdUkoNlW1Ub0Gx",
        ),
        access_notes="Public download (scientific/non-commercial usage).",
        expected_rules=(
            MarkerRule(
                kind="subject_dirs",
                candidates=("S*",),
                description="Subject folders S* should be present.",
            ),
            MarkerRule(
                kind="any_file_glob",
                candidates=("S*/labels.csv", "S*/label.csv", "S*/*.pkl"),
                description="At least one label source per subject (csv or pkl).",
            ),
        ),
    ),
    "emowear": DatasetSpec(
        dataset_id="emowear",
        title="EmoWear",
        download_urls=(
            "https://doi.org/10.5281/zenodo.10407278",
            "https://www.nature.com/articles/s41597-024-03429-3",
        ),
        access_notes="Zenodo package, check license/citation in record.",
        expected_rules=(
            MarkerRule(
                kind="participant_dirs",
                candidates=("*-*",),
                description="Participant folders <code>-<id> should be present.",
            ),
            MarkerRule(
                kind="any_path",
                candidates=("meta.csv", "questionnaire.csv", "sample.zip"),
                description="Expected metadata/sample files from release.",
            ),
        ),
    ),
    "grex": DatasetSpec(
        dataset_id="grex",
        title="G-REx",
        download_urls=(
            "https://zenodo.org/record/8136135",
            "https://forms.gle/RmMosk31zvvQRaUH7",
            "https://www.nature.com/articles/s41597-023-02905-6",
        ),
        access_notes="Requires EULA form completion before data access.",
        expected_rules=(
            MarkerRule(
                kind="all_paths",
                candidates=("1_Stimuli", "2_Questionnaire", "3_Physio", "4_Annotation", "5_Scripts", "6_Results"),
                description="Expected top-level G-REx structure should be present.",
            ),
            MarkerRule(
                kind="all_paths",
                candidates=(
                    "README.md",
                    "1_Stimuli/Raw/video_info.csv",
                    "1_Stimuli/Raw/video_info.json",
                    "2_Questionnaire/Raw/quest_raw_data.csv",
                    "2_Questionnaire/Raw/quest_raw_data.json",
                    "3_Physio/Transformed/physio_trans_data_session.pickle",
                    "3_Physio/Transformed/physio_trans_data_segments.pickle",
                    "4_Annotation/Transformed/ann_trans_data_segments.pickle",
                ),
                description="Expected raw/transformed metadata files from the G-REx release should be present.",
            ),
            MarkerRule(
                kind="all_file_globs",
                candidates=("3_Physio/Raw/*.hdf5",),
                description="Expected raw G-REx physio HDF5 files should be present.",
            ),
        ),
    ),
    "dapper": DatasetSpec(
        dataset_id="dapper",
        title="DAPPER",
        download_urls=(
            "https://doi.org/10.7303/syn22418021",
            "https://www.nature.com/articles/s41597-021-00945-4",
            "https://doi.org/10.6084/m9.figshare.13803185",
        ),
        access_notes="Synapse-hosted dataset; account/login may be required.",
        expected_rules=(
            MarkerRule(
                kind="participant_dirs",
                candidates=("[0-9]*",),
                description="Participant folders should be present.",
            ),
            MarkerRule(
                kind="all_file_globs",
                candidates=("**/*.csv", "**/*_ACC.csv", "**/*_GSR.csv", "**/*_PPG.csv"),
                description="Expected session CSVs and derived ACC/GSR/PPG streams should be present.",
            ),
        ),
    ),
}


def list_catalog() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for dataset_id in sorted(DATASET_SPECS):
        spec = DATASET_SPECS[dataset_id]
        rows.append(
            {
                "dataset_id": spec.dataset_id,
                "title": spec.title,
                "download_urls": list(spec.download_urls),
                "access_notes": spec.access_notes,
            }
        )
    return rows


def validate_source(dataset_id: str, source_dir: Path) -> ValidationResult:
    spec = DATASET_SPECS.get(dataset_id)
    if spec is None:
        return ValidationResult(
            dataset_id=dataset_id,
            source_dir=str(source_dir),
            status="failed",
            checks=[],
            warnings=[f"unsupported dataset_id: {dataset_id}"],
        )

    if not source_dir.exists() or not source_dir.is_dir():
        return ValidationResult(
            dataset_id=dataset_id,
            source_dir=str(source_dir),
            status="failed",
            checks=[],
            warnings=["source_dir does not exist or is not a directory"],
        )

    checks: list[dict[str, object]] = []
    failed_rules = 0

    for rule in spec.expected_rules:
        ok = _rule_passes(rule, source_dir)
        if not ok:
            failed_rules += 1
        checks.append(
            {
                "description": rule.description,
                "candidates": list(rule.candidates),
                "status": "pass" if ok else "fail",
            }
        )

    if failed_rules == 0:
        status = "passed"
    elif failed_rules < len(spec.expected_rules):
        status = "warning"
    else:
        status = "failed"

    return ValidationResult(
        dataset_id=dataset_id,
        source_dir=str(source_dir),
        status=status,
        checks=checks,
        warnings=[],
    )


def _rule_passes(rule: MarkerRule, source_dir: Path) -> bool:
    if rule.kind == "participant_dirs":
        for candidate in rule.candidates:
            if any(path.is_dir() for path in source_dir.glob(candidate)):
                return True
        return False

    if rule.kind == "subject_dirs":
        for candidate in rule.candidates:
            if any(path.is_dir() for path in source_dir.glob(candidate)):
                return True
        return False

    if rule.kind == "any_file_glob":
        for candidate in rule.candidates:
            if any(path.is_file() for path in source_dir.glob(candidate)):
                return True
        return False

    if rule.kind == "all_file_globs":
        for candidate in rule.candidates:
            if not any(path.is_file() for path in source_dir.glob(candidate)):
                return False
        return True

    if rule.kind == "any_path":
        for candidate in rule.candidates:
            if (source_dir / candidate).exists():
                return True
        return False

    if rule.kind == "all_paths":
        return all((source_dir / candidate).exists() for candidate in rule.candidates)

    return False


def inspect_source(dataset_id: str, source_dir: Path) -> InspectionResult:
    if dataset_id == "wesad":
        return _inspect_wesad(source_dir)
    if dataset_id == "emowear":
        return _inspect_emowear(source_dir)
    if dataset_id == "dapper":
        return _inspect_dapper(source_dir)
    if dataset_id == "grex":
        return _inspect_grex(source_dir)

    return InspectionResult(
        dataset_id=dataset_id,
        source_dir=str(source_dir),
        status="failed",
        summary={},
        checks=[],
        warnings=[f"unsupported dataset_id: {dataset_id}"],
    )


def _inspect_wesad(source_dir: Path) -> InspectionResult:
    validation = validate_source("wesad", source_dir)
    if validation.status == "failed":
        return InspectionResult(
            dataset_id="wesad",
            source_dir=str(source_dir),
            status="failed",
            summary={},
            checks=validation.checks,
            warnings=validation.warnings,
        )

    checks: list[dict[str, object]] = list(validation.checks)
    warnings: list[str] = []

    subject_dirs = sorted(path for path in source_dir.iterdir() if path.is_dir() and WESAD_SUBJECT_RE.match(path.name))
    observed_labels: set[int] = set()
    label_outliers: set[int] = set()
    subjects_inspected = 0
    shape_mismatch_count = 0
    quest_header_ok = True
    e4_dir_missing = 0

    for subject_dir in subject_dirs:
        subject_id = subject_dir.name
        pkl_path = subject_dir / f"{subject_id}.pkl"
        quest_path = subject_dir / f"{subject_id}_quest.csv"
        e4_dir = subject_dir / f"{subject_id}_E4_Data"

        if not e4_dir.exists():
            e4_dir_missing += 1

        if not quest_path.exists():
            quest_header_ok = False
        else:
            first_line = quest_path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
            if not first_line or not (first_line[0].startswith("# Subj;") or first_line[0].startswith("# Subj:;")):
                quest_header_ok = False

        if not pkl_path.exists():
            warnings.append(f"{subject_id}: missing pickle file")
            continue

        with pkl_path.open("rb") as handle:
            payload = pickle.load(handle, encoding="latin1")

        labels = _flatten_numeric_labels(payload.get("label"))
        observed_labels.update(labels)
        label_outliers.update(value for value in labels if value not in WESAD_ALLOWED_LABELS)

        signal = payload.get("signal", {})
        chest = signal.get("chest", {})
        wrist = signal.get("wrist", {})

        chest_keys = set(chest.keys())
        wrist_keys = set(wrist.keys())
        if chest_keys != WESAD_EXPECTED_CHEST_KEYS:
            warnings.append(f"{subject_id}: chest keys mismatch {sorted(chest_keys)}")
        if wrist_keys != WESAD_EXPECTED_WRIST_KEYS:
            warnings.append(f"{subject_id}: wrist keys mismatch {sorted(wrist_keys)}")

        label_count = _first_dim(payload.get("label"))
        for stream_name, values in chest.items():
            if _first_dim(values) != label_count:
                shape_mismatch_count += 1
                warnings.append(f"{subject_id}: chest stream {stream_name} first dimension does not match label count")

        subjects_inspected += 1
        del payload
        gc.collect()

    checks.append(
        {
            "description": "All subject pickle files expose only expected WESAD label values.",
            "status": "pass" if not label_outliers else "fail",
            "details": sorted(label_outliers),
        }
    )
    checks.append(
        {
            "description": "Chest stream lengths match label sequence length.",
            "status": "pass" if shape_mismatch_count == 0 else "fail",
            "details": {"shape_mismatch_count": shape_mismatch_count},
        }
    )
    checks.append(
        {
            "description": "Quest CSV files are present and parseable.",
            "status": "pass" if quest_header_ok else "warning",
        }
    )
    checks.append(
        {
            "description": "E4 directories are present for each subject.",
            "status": "pass" if e4_dir_missing == 0 else "warning",
            "details": {"missing_count": e4_dir_missing},
        }
    )

    status = _derive_status(checks, warnings)
    summary = {
        "subject_dir_count": len(subject_dirs),
        "subjects_inspected": subjects_inspected,
        "observed_label_values": sorted(observed_labels),
        "allowed_label_values": sorted(WESAD_ALLOWED_LABELS),
    }
    return InspectionResult(
        dataset_id="wesad",
        source_dir=str(source_dir),
        status=status,
        summary=summary,
        checks=checks,
        warnings=warnings,
    )


def _inspect_emowear(source_dir: Path) -> InspectionResult:
    validation = validate_source("emowear", source_dir)
    if validation.status == "failed":
        return InspectionResult(
            dataset_id="emowear",
            source_dir=str(source_dir),
            status="failed",
            summary={},
            checks=validation.checks,
            warnings=validation.warnings,
        )

    checks: list[dict[str, object]] = list(validation.checks)
    warnings: list[str] = []

    participant_dirs = sorted(
        path for path in source_dir.iterdir() if path.is_dir() and EMOWEAR_PARTICIPANT_RE.match(path.name)
    )
    meta_path = source_dir / "meta.csv"
    questionnaire_path = source_dir / "questionnaire.csv"
    mqtt_db_path = source_dir / "mqtt.db"

    meta_rows = _read_csv_rows(meta_path) if meta_path.exists() else []
    questionnaire_rows = _read_csv_rows(questionnaire_path) if questionnaire_path.exists() else []
    meta_header = meta_rows[0] if meta_rows else []
    questionnaire_header = questionnaire_rows[0] if questionnaire_rows else []
    meta_ids = {row[1] for row in meta_rows[1:] if len(row) > 1}
    questionnaire_ids = {row[1] for row in questionnaire_rows[1:] if len(row) > 1}
    participant_ids = {path.name.split("-", 1)[1] for path in participant_dirs if "-" in path.name}

    missing_required_archives = 0
    missing_required_members = 0
    parsed_participants = 0

    for participant_dir in participant_dirs:
        e4_path = participant_dir / "e4.zip"
        bh3_path = participant_dir / "bh3.zip"
        if not e4_path.exists() or not bh3_path.exists():
            missing_required_archives += 1
            warnings.append(f"{participant_dir.name}: missing e4.zip or bh3.zip")
            continue

        if not _zip_contains_all(e4_path, EMOWEAR_REQUIRED_E4_MEMBERS):
            missing_required_members += 1
            warnings.append(f"{participant_dir.name}: e4.zip is missing one or more expected members")
        if not _zip_contains_suffixes(bh3_path, EMOWEAR_REQUIRED_BH3_SUFFIXES):
            missing_required_members += 1
            warnings.append(f"{participant_dir.name}: bh3.zip is missing one or more expected members")

        if not _emowear_zip_members_are_parseable(e4_path, bh3_path):
            missing_required_members += 1
            warnings.append(f"{participant_dir.name}: zip contents are not parseable with expected header layout")
        parsed_participants += 1

    mqtt_db_ok = _sqlite_has_tables(mqtt_db_path)
    checks.append(
        {
            "description": "meta.csv header matches the expected EmoWear release schema.",
            "status": "pass" if meta_header == EMOWEAR_META_HEADER else "fail",
        }
    )
    checks.append(
        {
            "description": "questionnaire.csv header matches the expected EmoWear release schema.",
            "status": "pass" if questionnaire_header == EMOWEAR_QUESTIONNAIRE_HEADER else "fail",
        }
    )
    checks.append(
        {
            "description": "Participant IDs match meta/questionnaire tables.",
            "status": "pass" if participant_ids == meta_ids == questionnaire_ids else "warning",
            "details": {
                "participant_count": len(participant_ids),
                "meta_id_count": len(meta_ids),
                "questionnaire_id_count": len(questionnaire_ids),
            },
        }
    )
    checks.append(
        {
            "description": "Each participant contains parseable e4.zip and bh3.zip payloads.",
            "status": "pass" if missing_required_archives == 0 and missing_required_members == 0 else "warning",
            "details": {
                "missing_required_archives": missing_required_archives,
                "missing_required_members": missing_required_members,
            },
        }
    )
    checks.append(
        {
            "description": "mqtt.db is present and opens as SQLite.",
            "status": "pass" if mqtt_db_ok else "warning",
        }
    )

    status = _derive_status(checks, warnings)
    summary = {
        "participant_dir_count": len(participant_dirs),
        "participants_inspected": parsed_participants,
        "meta_row_count": max(0, len(meta_rows) - 1),
        "questionnaire_row_count": max(0, len(questionnaire_rows) - 1),
        "optional_sensor_archives": {
            "front_zip_count": _count_existing(participant_dirs, "front.zip"),
            "back_zip_count": _count_existing(participant_dirs, "back.zip"),
            "water_zip_count": _count_existing(participant_dirs, "water.zip"),
        },
    }
    return InspectionResult(
        dataset_id="emowear",
        source_dir=str(source_dir),
        status=status,
        summary=summary,
        checks=checks,
        warnings=warnings,
    )


def _inspect_dapper(source_dir: Path) -> InspectionResult:
    validation = validate_source("dapper", source_dir)
    if validation.status == "failed":
        return InspectionResult(
            dataset_id="dapper",
            source_dir=str(source_dir),
            status="failed",
            summary={},
            checks=validation.checks,
            warnings=validation.warnings,
        )

    checks: list[dict[str, object]] = list(validation.checks)
    warnings: list[str] = []

    participant_dirs = sorted(path for path in source_dir.iterdir() if path.is_dir() and path.name.isdigit())
    session_group_mismatches = 0
    header_mismatches = 0
    parse_failures = 0
    empty_file_count = 0
    total_session_groups = 0

    for participant_dir in participant_dirs:
        groups = _collect_dapper_groups(participant_dir)
        total_session_groups += len(groups)
        for prefix, kinds in groups.items():
            if kinds != {"base", "acc", "gsr", "ppg"}:
                session_group_mismatches += 1
                warnings.append(f"{participant_dir.name}: session {prefix} does not have the full base/acc/gsr/ppg set")

        for csv_path in participant_dir.glob("*.csv"):
            kind = _dapper_kind(csv_path.name)
            if csv_path.stat().st_size == 0:
                empty_file_count += 1
                warnings.append(f"{participant_dir.name}: zero-byte sensor file {csv_path.name}")
                continue
            expected_header = DAPPER_REQUIRED_HEADERS[kind]
            header = _read_csv_header(csv_path)
            if header != expected_header:
                header_mismatches += 1
                warnings.append(f"{participant_dir.name}: header mismatch in {csv_path.name}")
                continue
            if not _dapper_first_row_is_parseable(csv_path, kind):
                parse_failures += 1
                warnings.append(f"{participant_dir.name}: first data row failed type parsing in {csv_path.name}")

    checks.append(
        {
            "description": "Each DAPPER session prefix has base/ACC/GSR/PPG companions.",
            "status": "pass" if session_group_mismatches == 0 else "warning",
            "details": {"session_group_mismatches": session_group_mismatches},
        }
    )
    checks.append(
        {
            "description": "All DAPPER CSV headers match the observed release schema.",
            "status": "pass" if header_mismatches == 0 else "fail",
            "details": {"header_mismatches": header_mismatches},
        }
    )
    checks.append(
        {
            "description": "No zero-byte DAPPER sensor files are present.",
            "status": "pass" if empty_file_count == 0 else "warning",
            "details": {"empty_file_count": empty_file_count},
        }
    )
    checks.append(
        {
            "description": "First data rows parse into numeric/time values for every DAPPER CSV.",
            "status": "pass" if parse_failures == 0 else "warning",
            "details": {"parse_failures": parse_failures},
        }
    )

    status = _derive_status(checks, warnings)
    summary = {
        "participant_dir_count": len(participant_dirs),
        "session_group_count": total_session_groups,
        "readme_present": (source_dir / "README.txt").exists(),
        "session_group_mismatches": session_group_mismatches,
        "empty_file_count": empty_file_count,
    }
    return InspectionResult(
        dataset_id="dapper",
        source_dir=str(source_dir),
        status=status,
        summary=summary,
        checks=checks,
        warnings=warnings,
    )


def _inspect_grex(source_dir: Path) -> InspectionResult:
    validation = validate_source("grex", source_dir)
    if validation.status == "failed":
        return InspectionResult(
            dataset_id="grex",
            source_dir=str(source_dir),
            status="failed",
            summary={},
            checks=validation.checks,
            warnings=validation.warnings,
        )

    checks: list[dict[str, object]] = list(validation.checks)
    warnings: list[str] = []

    video_rows = _read_csv_rows(source_dir / "1_Stimuli/Raw/video_info.csv")
    questionnaire_rows = _read_csv_rows(source_dir / "2_Questionnaire/Raw/quest_raw_data.csv")
    video_header = video_rows[0] if video_rows else []
    questionnaire_header = questionnaire_rows[0] if questionnaire_rows else []
    video_json = _load_json(source_dir / "1_Stimuli/Raw/video_info.json")
    questionnaire_json = _load_json(source_dir / "2_Questionnaire/Raw/quest_raw_data.json")

    stimu_session = _load_pickle_object(source_dir / "1_Stimuli/Transformed/stimu_trans_data_session.pickle")
    stimu_segments = _load_pickle_object(source_dir / "1_Stimuli/Transformed/stimu_trans_data_segments.pickle")
    quest_session = _load_pickle_object(source_dir / "2_Questionnaire/Transformed/quest_trans_data_session.pickle")
    quest_segments = _load_pickle_object(source_dir / "2_Questionnaire/Transformed/quest_trans_data_segments.pickle")
    physio_session = _load_pickle_object(source_dir / "3_Physio/Transformed/physio_trans_data_session.pickle")
    physio_segments = _load_pickle_object(source_dir / "3_Physio/Transformed/physio_trans_data_segments.pickle")
    ann_segments = _load_pickle_object(source_dir / "4_Annotation/Transformed/ann_trans_data_segments.pickle")

    session_count = _sequence_length(stimu_session, "session")
    segment_count = _sequence_length(stimu_segments, "session")
    raw_hdf5_paths = sorted((source_dir / "3_Physio/Raw").glob("*.hdf5"))
    invalid_raw_filenames = [path.name for path in raw_hdf5_paths if not GREX_PHYSIO_RAW_RE.match(path.name)]
    invalid_hdf5_magic = [path.name for path in raw_hdf5_paths if not _has_binary_prefix(path, GREX_HDF5_MAGIC)]
    sampled_raw_paths = raw_hdf5_paths[: min(3, len(raw_hdf5_paths))]
    sampled_hdf5_token_failures = [
        path.name for path in sampled_raw_paths if not _binary_contains_all(path, GREX_REQUIRED_HDF5_TOKENS, max_bytes=1_048_576)
    ]

    session_alignment_ok = (
        session_count > 0
        and _mapping_has_keys(stimu_session, GREX_STIMULI_KEYS)
        and _mapping_has_keys(quest_session, GREX_QUESTIONNAIRE_KEYS)
        and _mapping_has_keys(physio_session, GREX_PHYSIO_SEQUENCE_KEYS | GREX_PHYSIO_AUX_KEYS)
        and _all_mapping_values_have_length(stimu_session, GREX_STIMULI_KEYS, session_count)
        and _all_mapping_values_have_length(quest_session, GREX_QUESTIONNAIRE_KEYS, session_count)
        and _all_mapping_values_have_length(physio_session, GREX_PHYSIO_SEQUENCE_KEYS, session_count)
    )
    segment_alignment_ok = (
        segment_count > 0
        and _mapping_has_keys(stimu_segments, GREX_STIMULI_KEYS)
        and _mapping_has_keys(quest_segments, GREX_QUESTIONNAIRE_KEYS)
        and _mapping_has_keys(physio_segments, GREX_PHYSIO_SEQUENCE_KEYS | GREX_PHYSIO_AUX_KEYS)
        and _mapping_has_keys(ann_segments, GREX_ANNOTATION_KEYS)
        and _all_mapping_values_have_length(stimu_segments, GREX_STIMULI_KEYS, segment_count)
        and _all_mapping_values_have_length(quest_segments, GREX_QUESTIONNAIRE_KEYS, segment_count)
        and _all_mapping_values_have_length(physio_segments, GREX_PHYSIO_SEQUENCE_KEYS, segment_count)
        and _all_mapping_values_have_length(ann_segments, GREX_ANNOTATION_KEYS, segment_count)
    )
    results_dirs = [
        str(path.relative_to(source_dir))
        for path in sorted((source_dir / "6_Results").iterdir())
        if path.is_dir() and path.name != "__MACOSX"
    ]

    checks.append(
        {
            "description": "video_info.csv header matches the observed G-REx release schema.",
            "status": "pass" if video_header == GREX_VIDEO_INFO_HEADER else "fail",
        }
    )
    checks.append(
        {
            "description": "quest_raw_data.csv header matches the observed G-REx release schema.",
            "status": "pass" if questionnaire_header == GREX_QUESTIONNAIRE_HEADER else "fail",
        }
    )
    checks.append(
        {
            "description": "CSV and JSON metadata counts align for stimuli and questionnaire tables.",
            "status": "pass"
            if _json_record_count(video_json) == max(0, len(video_rows) - 1)
            and _json_record_count(questionnaire_json) == max(0, len(questionnaire_rows) - 1)
            else "warning",
            "details": {
                "video_csv_count": max(0, len(video_rows) - 1),
                "video_json_count": _json_record_count(video_json),
                "questionnaire_csv_count": max(0, len(questionnaire_rows) - 1),
                "questionnaire_json_count": _json_record_count(questionnaire_json),
            },
        }
    )
    checks.append(
        {
            "description": "Transformed G-REx pickles expose the expected key sets.",
            "status": "pass"
            if _mapping_has_keys(stimu_session, GREX_STIMULI_KEYS)
            and _mapping_has_keys(stimu_segments, GREX_STIMULI_KEYS)
            and _mapping_has_keys(quest_session, GREX_QUESTIONNAIRE_KEYS)
            and _mapping_has_keys(quest_segments, GREX_QUESTIONNAIRE_KEYS)
            and _mapping_has_keys(physio_session, GREX_PHYSIO_SEQUENCE_KEYS | GREX_PHYSIO_AUX_KEYS)
            and _mapping_has_keys(physio_segments, GREX_PHYSIO_SEQUENCE_KEYS | GREX_PHYSIO_AUX_KEYS)
            and _mapping_has_keys(ann_segments, GREX_ANNOTATION_KEYS)
            else "fail",
        }
    )
    checks.append(
        {
            "description": "Session-level transformed artifacts align across stimuli/questionnaire/physio.",
            "status": "pass" if session_alignment_ok else "fail",
            "details": {"session_count": session_count},
        }
    )
    checks.append(
        {
            "description": "Segment-level transformed artifacts align across stimuli/questionnaire/physio/annotation.",
            "status": "pass" if segment_alignment_ok else "fail",
            "details": {"segment_count": segment_count},
        }
    )
    checks.append(
        {
            "description": "Raw physio filenames match the observed G-REx naming scheme and have HDF5 magic bytes.",
            "status": "pass" if not invalid_raw_filenames and not invalid_hdf5_magic else "fail",
            "details": {
                "raw_hdf5_count": len(raw_hdf5_paths),
                "invalid_raw_filenames": invalid_raw_filenames,
                "invalid_hdf5_magic": invalid_hdf5_magic,
            },
        }
    )
    checks.append(
        {
            "description": "Sampled raw HDF5 files contain expected embedded dataset tokens used by the bundled scripts.",
            "status": "pass" if not sampled_hdf5_token_failures else "warning",
            "details": {
                "sampled_file_count": len(sampled_raw_paths),
                "sampled_hdf5_token_failures": sampled_hdf5_token_failures,
            },
        }
    )
    checks.append(
        {
            "description": "Result subdirectories for EDA, PPG, and Analysis are present.",
            "status": "pass" if {"6_Results/EDA", "6_Results/PPG", "6_Results/Analysis"}.issubset(set(results_dirs)) else "warning",
            "details": {"results_dirs": results_dirs},
        }
    )

    status = _derive_status(checks, warnings)
    summary = {
        "movie_count": max(0, len(video_rows) - 1),
        "questionnaire_row_count": max(0, len(questionnaire_rows) - 1),
        "physio_raw_hdf5_count": len(raw_hdf5_paths),
        "session_count": session_count,
        "segment_count": segment_count,
    }
    return InspectionResult(
        dataset_id="grex",
        source_dir=str(source_dir),
        status=status,
        summary=summary,
        checks=checks,
        warnings=warnings,
    )


def _derive_status(checks: list[dict[str, object]], warnings: list[str]) -> str:
    if any(check["status"] == "fail" for check in checks):
        return "failed"
    if warnings or any(check["status"] == "warning" for check in checks):
        return "warning"
    return "passed"


def _read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return next(csv.reader(handle), [])


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return list(csv.reader(handle))


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return json.load(handle)


def _load_pickle_object(path: Path) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with path.open("rb") as handle:
            return pickle.load(handle)


def _json_record_count(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload)
    return 0


def _mapping_has_keys(payload: object, expected_keys: set[str]) -> bool:
    return isinstance(payload, dict) and expected_keys.issubset(set(payload.keys()))


def _sequence_length(payload: object, key: str) -> int:
    if not isinstance(payload, dict):
        return 0
    values = payload.get(key)
    try:
        return len(values)
    except TypeError:
        return 0


def _all_mapping_values_have_length(payload: object, keys: set[str], expected_length: int) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in keys:
        try:
            if len(payload[key]) != expected_length:
                return False
        except (KeyError, TypeError):
            return False
    return True


def _has_binary_prefix(path: Path, prefix: bytes) -> bool:
    with path.open("rb") as handle:
        return handle.read(len(prefix)) == prefix


def _binary_contains_all(path: Path, patterns: tuple[str, ...], max_bytes: int) -> bool:
    wanted = [pattern.encode("utf-8") for pattern in patterns]
    longest = max(len(pattern) for pattern in wanted)
    remaining = set(wanted)
    consumed = 0
    tail = b""

    with path.open("rb") as handle:
        while remaining and consumed < max_bytes:
            chunk = handle.read(min(65_536, max_bytes - consumed))
            if not chunk:
                break
            consumed += len(chunk)
            data = tail + chunk
            remaining = {pattern for pattern in remaining if pattern not in data}
            tail = data[-(longest - 1) :] if longest > 1 else b""

    return not remaining


def _flatten_numeric_labels(values: Any) -> set[int]:
    if np is not None:
        array = np.asarray(values).reshape(-1)
        return {int(value) for value in np.unique(array).tolist()}

    if values is None:
        return set()

    flattened: set[int] = set()
    for value in values:
        try:
            flattened.add(int(value))
        except (TypeError, ValueError):
            continue
    return flattened


def _first_dim(values: Any) -> int:
    shape = getattr(values, "shape", None)
    if shape:
        return int(shape[0])
    try:
        return len(values)
    except TypeError:
        return 0


def _zip_contains_all(path: Path, members: set[str]) -> bool:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    return members.issubset(names)


def _zip_contains_suffixes(path: Path, suffixes: set[str]) -> bool:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    for suffix in suffixes:
        if not any(name.endswith(suffix) for name in names):
            return False
    return True


def _emowear_zip_members_are_parseable(e4_path: Path, bh3_path: Path) -> bool:
    try:
        with zipfile.ZipFile(e4_path) as archive:
            acc_lines = _read_zip_lines(archive, "ACC.csv", 3)
            ibi_lines = _read_zip_lines(archive, "IBI.csv", 2)
        with zipfile.ZipFile(bh3_path) as archive:
            ecg_member = _find_member_ending_with(archive, "_ECG.csv")
            event_member = _find_member_ending_with(archive, "_Event_Data.csv")
            if ecg_member is None or event_member is None:
                return False
            ecg_lines = _read_zip_lines(archive, ecg_member, 2)
            event_lines = _read_zip_lines(archive, event_member, 2)
    except (KeyError, zipfile.BadZipFile):
        return False

    return (
        len(acc_lines) >= 3
        and len(ibi_lines) >= 2
        and len(ecg_lines) >= 2
        and len(event_lines) >= 2
        and _line_has_comma_columns(acc_lines[0], 3)
        and _line_has_comma_columns(acc_lines[1], 3)
        and _line_has_comma_columns(ibi_lines[0], 2)
        and ecg_lines[0] == "Time,EcgWaveform"
        and event_lines[0].startswith("SeqNo")
    )


def _read_zip_lines(archive: zipfile.ZipFile, member: str, line_count: int) -> list[str]:
    lines: list[str] = []
    with archive.open(member) as handle:
        for _ in range(line_count):
            raw_line = handle.readline()
            if not raw_line:
                break
            lines.append(raw_line.decode("utf-8", errors="replace").strip())
    return lines


def _find_member_ending_with(archive: zipfile.ZipFile, suffix: str) -> Optional[str]:
    for name in archive.namelist():
        if name.endswith(suffix):
            return name
    return None


def _line_has_comma_columns(line: str, count: int) -> bool:
    return len([part for part in line.split(",")]) == count


def _sqlite_has_tables(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with sqlite3.connect(str(path)) as connection:
            cur = connection.cursor()
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'")
            row = cur.fetchone()
            return bool(row and row[0] > 0)
    except sqlite3.DatabaseError:
        return False


def _count_existing(paths: list[Path], filename: str) -> int:
    return sum(1 for path in paths if (path / filename).exists())


def _collect_dapper_groups(participant_dir: Path) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = {}
    for csv_path in participant_dir.glob("*.csv"):
        kind = _dapper_kind(csv_path.name)
        prefix = _dapper_prefix(csv_path.name)
        groups.setdefault(prefix, set()).add(kind)
    return groups


def _dapper_kind(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith("_acc.csv"):
        return "acc"
    if lowered.endswith("_gsr.csv"):
        return "gsr"
    if lowered.endswith("_ppg.csv"):
        return "ppg"
    return "base"


def _dapper_prefix(filename: str) -> str:
    lowered = filename.lower()
    for suffix in ("_acc.csv", "_gsr.csv", "_ppg.csv", ".csv"):
        if lowered.endswith(suffix):
            return filename[: -len(suffix)]
    return filename


def _dapper_first_row_is_parseable(path: Path, kind: str) -> bool:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        row = next(reader, None)

    if not row:
        return False

    try:
        if kind == "base":
            float(row[0])
            float(row[1])
            float(row[2])
            float(row[3])
            return _parse_datetime(row[4], ("%Y/%m/%d %H:%M:%S",)) is not None
        if kind == "acc":
            float(row[0])
            float(row[1])
            float(row[2])
            return _parse_datetime(row[3], ("%Y-%m-%d %H:%M:%S",)) is not None
        if kind in {"gsr", "ppg"}:
            float(row[0])
            return _parse_datetime(row[1], ("%Y-%m-%d %H:%M:%S",)) is not None
    except (ValueError, IndexError):
        return False

    return False


def _parse_datetime(value: str, formats: tuple[str, ...]) -> Optional[str]:
    from datetime import datetime

    for format_value in formats:
        try:
            datetime.strptime(value, format_value)
            return value
        except ValueError:
            continue
    return None
