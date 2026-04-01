#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> None:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:  # pragma: no cover - tool availability check
        raise RuntimeError("jsonschema package is required for contract validation") from exc

    schema = _load_json(args.schema)
    validator = Draft202012Validator(schema)

    targets = [args.example]
    if args.snapshot.exists():
        targets.append(args.snapshot)

    for target in targets:
        payload = _load_json(target)
        errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
        if errors:
            details = "; ".join(f"{'/'.join(str(item) for item in err.path)}: {err.message}" for err in errors)
            raise ValueError(f"Schema validation failed for {target}: {details}")
        print(f"OK: {target}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate valence canary dashboard snapshot against schema")
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/contracts/operations/valence-canary-dashboard.schema.json"),
    )
    parser.add_argument(
        "--example",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/contracts/operations/examples/valence-canary-dashboard.example.json"),
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/dashboard-snapshot.json"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
