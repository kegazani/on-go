from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dataset_registry.catalog import inspect_source, list_catalog, validate_source
from dataset_registry.external_imports import (
    import_dapper_dataset,
    import_emowear_dataset,
    import_grex_dataset,
)
from dataset_registry.models import DatasetRecord
from dataset_registry.registry import DatasetRegistry
from dataset_registry.wesad import import_wesad_dataset


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dataset registry and external dataset ingestion tools")
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="Register or update a dataset version record")
    register.add_argument("--registry-path", required=True)
    register.add_argument("--dataset-id", required=True)
    register.add_argument("--dataset-version", required=True)
    register.add_argument("--source", required=True)
    register.add_argument("--source-uri", default=None)
    register.add_argument("--source-license", default=None)
    register.add_argument("--ingestion-script-version", required=True)
    register.add_argument("--preprocessing-version", required=True)
    register.add_argument("--split-strategy", default="subject-wise")
    register.add_argument("--target-track", action="append", dest="target_tracks", default=[])
    register.add_argument("--label", action="append", dest="labels_available", default=[])
    register.add_argument("--modality", action="append", dest="modalities_available", default=[])
    register.add_argument("--row-count", type=int, default=0)
    register.add_argument("--subject-count", type=int, default=0)
    register.add_argument("--session-count", type=int, default=0)
    register.add_argument("--metadata-object", required=True)

    list_cmd = sub.add_parser("list", help="List dataset records")
    list_cmd.add_argument("--registry-path", required=True)

    sub.add_parser("dataset-catalog", help="List supported external datasets and download references")

    validate = sub.add_parser("validate-source", help="Validate local source directory for a dataset")
    validate.add_argument("--dataset-id", required=True, choices=["wesad", "emowear", "grex", "dapper"])
    validate.add_argument("--source-dir", required=True)

    inspect_cmd = sub.add_parser("inspect-source", help="Inspect real dataset structure, headers, labels, and parseability")
    inspect_cmd.add_argument("--dataset-id", required=True, choices=["wesad", "emowear", "grex", "dapper"])
    inspect_cmd.add_argument("--source-dir", required=True)

    wesad = sub.add_parser("import-wesad", help="Import WESAD into unified internal schema")
    wesad.add_argument("--registry-path", required=True)
    wesad.add_argument("--source-dir", required=True)
    wesad.add_argument("--output-dir", required=True)
    wesad.add_argument("--dataset-version", default="wesad-v1")
    wesad.add_argument("--preprocessing-version", default="e2-v1")
    wesad.add_argument("--source-uri", default=None)
    wesad.add_argument("--source-license", default=None)

    emowear = sub.add_parser("import-emowear", help="Import EmoWear into unified internal schema")
    emowear.add_argument("--registry-path", required=True)
    emowear.add_argument("--source-dir", required=True)
    emowear.add_argument("--output-dir", required=True)
    emowear.add_argument("--dataset-version", default="emowear-v1")
    emowear.add_argument("--preprocessing-version", default="e2-v1")
    emowear.add_argument("--source-uri", default=None)
    emowear.add_argument("--source-license", default=None)

    grex = sub.add_parser("import-grex", help="Import G-REx transformed artifacts into unified internal schema")
    grex.add_argument("--registry-path", required=True)
    grex.add_argument("--source-dir", required=True)
    grex.add_argument("--output-dir", required=True)
    grex.add_argument("--dataset-version", default="grex-v1")
    grex.add_argument("--preprocessing-version", default="e2-v1")
    grex.add_argument("--source-uri", default=None)
    grex.add_argument("--source-license", default=None)

    dapper = sub.add_parser("import-dapper", help="Import DAPPER into unified internal schema (proxy labels)")
    dapper.add_argument("--registry-path", required=True)
    dapper.add_argument("--source-dir", required=True)
    dapper.add_argument("--output-dir", required=True)
    dapper.add_argument("--dataset-version", default="dapper-v1")
    dapper.add_argument("--preprocessing-version", default="e2-v1")
    dapper.add_argument("--source-uri", default=None)
    dapper.add_argument("--source-license", default=None)

    return parser


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "register":
        _run_register(args)
        return

    if args.command == "list":
        _run_list(args)
        return

    if args.command == "dataset-catalog":
        _run_dataset_catalog()
        return

    if args.command == "validate-source":
        _run_validate_source(args)
        return

    if args.command == "inspect-source":
        _run_inspect_source(args)
        return

    if args.command == "import-wesad":
        _run_import_wesad(args)
        return

    if args.command == "import-emowear":
        _run_import_emowear(args)
        return

    if args.command == "import-grex":
        _run_import_grex(args)
        return

    if args.command == "import-dapper":
        _run_import_dapper(args)
        return

    parser.error(f"Unsupported command: {args.command}")


def _run_register(args: argparse.Namespace) -> None:
    registry = DatasetRegistry(Path(args.registry_path))
    record = DatasetRecord(
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
        source=args.source,
        source_uri=args.source_uri,
        source_license=args.source_license,
        ingestion_script_version=args.ingestion_script_version,
        preprocessing_version=args.preprocessing_version,
        split_strategy=args.split_strategy,
        target_tracks=args.target_tracks,
        labels_available=args.labels_available,
        modalities_available=args.modalities_available,
        row_count=max(0, int(args.row_count)),
        subject_count=max(0, int(args.subject_count)),
        session_count=max(0, int(args.session_count)),
        created_at_utc=datetime.now(timezone.utc),
        metadata_object=args.metadata_object,
    )
    registry.upsert(record)
    print(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2))


def _run_list(args: argparse.Namespace) -> None:
    registry = DatasetRegistry(Path(args.registry_path))
    payload = [record.model_dump(mode="json") for record in registry.list_records()]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_dataset_catalog() -> None:
    print(json.dumps(list_catalog(), ensure_ascii=False, indent=2))


def _run_validate_source(args: argparse.Namespace) -> None:
    result = validate_source(dataset_id=args.dataset_id, source_dir=Path(args.source_dir))
    payload = {
        "dataset_id": result.dataset_id,
        "source_dir": result.source_dir,
        "status": result.status,
        "checks": result.checks,
        "warnings": result.warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if result.status == "failed":
        raise SystemExit(1)


def _run_inspect_source(args: argparse.Namespace) -> None:
    result = inspect_source(dataset_id=args.dataset_id, source_dir=Path(args.source_dir))
    payload = {
        "dataset_id": result.dataset_id,
        "source_dir": result.source_dir,
        "status": result.status,
        "summary": result.summary,
        "checks": result.checks,
        "warnings": result.warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if result.status == "failed":
        raise SystemExit(1)


def _run_import_wesad(args: argparse.Namespace) -> None:
    registry_path = Path(args.registry_path)
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)

    result = import_wesad_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        dataset_version=args.dataset_version,
        preprocessing_version=args.preprocessing_version,
        source_uri=args.source_uri,
        source_license=args.source_license,
    )

    registry = DatasetRegistry(registry_path)
    registry.upsert(result.record)

    payload = {
        "status": "completed",
        "dataset_id": result.record.dataset_id,
        "dataset_version": result.record.dataset_version,
        "subject_count": len(result.subjects),
        "session_count": len(result.sessions),
        "segment_label_count": len(result.segment_labels),
        "metadata_object": result.record.metadata_object,
        "warnings": result.warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_import_emowear(args: argparse.Namespace) -> None:
    result = import_emowear_dataset(
        source_dir=Path(args.source_dir),
        output_dir=Path(args.output_dir),
        dataset_version=args.dataset_version,
        preprocessing_version=args.preprocessing_version,
        source_uri=args.source_uri,
        source_license=args.source_license,
    )
    registry = DatasetRegistry(Path(args.registry_path))
    registry.upsert(result.record)
    _print_import_payload(result)


def _run_import_grex(args: argparse.Namespace) -> None:
    result = import_grex_dataset(
        source_dir=Path(args.source_dir),
        output_dir=Path(args.output_dir),
        dataset_version=args.dataset_version,
        preprocessing_version=args.preprocessing_version,
        source_uri=args.source_uri,
        source_license=args.source_license,
    )
    registry = DatasetRegistry(Path(args.registry_path))
    registry.upsert(result.record)
    _print_import_payload(result)


def _run_import_dapper(args: argparse.Namespace) -> None:
    result = import_dapper_dataset(
        source_dir=Path(args.source_dir),
        output_dir=Path(args.output_dir),
        dataset_version=args.dataset_version,
        preprocessing_version=args.preprocessing_version,
        source_uri=args.source_uri,
        source_license=args.source_license,
    )
    registry = DatasetRegistry(Path(args.registry_path))
    registry.upsert(result.record)
    _print_import_payload(result)


def _print_import_payload(result: object) -> None:
    payload = {
        "status": "completed",
        "dataset_id": result.record.dataset_id,
        "dataset_version": result.record.dataset_version,
        "subject_count": len(result.subjects),
        "session_count": len(result.sessions),
        "segment_label_count": len(result.segment_labels),
        "metadata_object": result.record.metadata_object,
        "warnings": result.warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
