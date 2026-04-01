from __future__ import annotations

import argparse
import json
import sys

from signal_processing_worker.config import Settings
from signal_processing_worker.db import Database
from signal_processing_worker.errors import WorkerError
from signal_processing_worker.service import SignalProcessingService
from signal_processing_worker.storage import S3Storage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run E1/E2 preprocessing and feature extraction for a raw session")
    parser.add_argument("--session-id", required=True, help="Raw session_id to preprocess")
    parser.add_argument(
        "--preprocessing-version",
        required=False,
        default=None,
        help="Override preprocessing version tag (default: env SPW_PREPROCESSING_VERSION)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute preprocessing summary without writing clean artifacts",
    )
    return parser


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    settings = Settings.from_env()
    persist_outputs = settings.persist_outputs and not args.dry_run

    service = SignalProcessingService(
        database=Database(settings.database_dsn),
        storage=S3Storage(settings),
        clean_root_prefix=settings.clean_root_prefix,
        preprocessing_version=settings.preprocessing_version,
        gap_factor=settings.gap_factor,
        max_samples_per_stream=settings.max_samples_per_stream,
        persist_outputs=persist_outputs,
    )

    try:
        result = service.process_session(
            session_id=args.session_id,
            preprocessing_version=args.preprocessing_version,
        )
    except WorkerError as exc:
        payload = {
            "status": "failed",
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)

    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
