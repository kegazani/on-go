#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def run(args: argparse.Namespace) -> dict[str, Any]:
    snapshot = json.loads(args.snapshot_json.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)

    generated = _parse_utc(snapshot.get("generated_at_utc"))
    age_minutes = None
    if generated is not None:
        age_minutes = (now - generated).total_seconds() / 60.0
    is_fresh = age_minutes is not None and age_minutes <= float(args.freshness_slo_minutes)

    runtime_response = {
        "loaded": True,
        "freshness_slo_minutes": args.freshness_slo_minutes,
        "is_fresh": bool(is_fresh),
        "snapshot": snapshot,
    }

    report = {
        "experiment_id": f"e2-16-runtime-dashboard-dryrun-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "snapshot_path": str(args.snapshot_json),
        "freshness_slo_minutes": args.freshness_slo_minutes,
        "snapshot_age_minutes": age_minutes,
        "is_fresh": bool(is_fresh),
        "decision": "serve_snapshot" if is_fresh else "serve_snapshot_with_stale_flag",
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "runtime-dashboard-response.json").write_text(
        json.dumps(runtime_response, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.16 Runtime Dashboard Endpoint Dry-Run",
                "",
                f"- Snapshot freshness SLO: `{args.freshness_slo_minutes} min`",
                f"- Snapshot age: `{age_minutes}`",
                f"- Is fresh: `{is_fresh}`",
                f"- Decision: `{report['decision']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.16 runtime dashboard endpoint dry-run")
    parser.add_argument(
        "--snapshot-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/dashboard-snapshot.json"
        ),
    )
    parser.add_argument("--freshness-slo-minutes", type=int, default=120)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-16-runtime-dashboard-endpoint"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
