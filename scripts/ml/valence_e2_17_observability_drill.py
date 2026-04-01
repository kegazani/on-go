#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _run_cmd(cmd: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "ok": proc.returncode == 0,
    }


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
    repo_root = args.repo_root

    steps = [
        _run_cmd(["python3", "scripts/ml/valence_e2_13_canary_hardening.py", "--check-interval-minutes", "60"], cwd=repo_root),
        _run_cmd(["python3", "scripts/ml/valence_e2_15_scheduler_dashboard.py"], cwd=repo_root),
        _run_cmd(["python3", "scripts/contracts/validate_valence_canary_snapshot.py"], cwd=repo_root),
    ]

    canary_state = json.loads(args.canary_state_json.read_text(encoding="utf-8"))
    snapshot = json.loads(args.dashboard_snapshot_json.read_text(encoding="utf-8"))
    policy = json.loads(args.policy_json.read_text(encoding="utf-8"))
    alerts = json.loads(args.alerts_json.read_text(encoding="utf-8"))

    api_src = repo_root / "services" / "inference-api" / "src"
    if str(api_src) not in sys.path:
        sys.path.insert(0, str(api_src))

    from inference_api.api import _effective_mode, _is_dashboard_fresh  # type: ignore

    effective_mode = _effective_mode(policy=policy, canary_state=canary_state)
    is_fresh = _is_dashboard_fresh(snapshot=snapshot, freshness_slo_minutes=args.freshness_slo_minutes)

    runtime_response = {
        "loaded": True,
        "freshness_slo_minutes": args.freshness_slo_minutes,
        "is_fresh": bool(is_fresh),
        "snapshot": snapshot,
    }

    checks = [
        {
            "item": "scheduler_cycle_completed",
            "status": "pass" if steps[0]["ok"] and steps[1]["ok"] else "fail",
            "details": "E2.13 and E2.15 scripts executed",
        },
        {
            "item": "canary_state_present",
            "status": "pass" if args.canary_state_json.exists() else "fail",
            "details": str(args.canary_state_json),
        },
        {
            "item": "dashboard_snapshot_present",
            "status": "pass" if args.dashboard_snapshot_json.exists() else "fail",
            "details": str(args.dashboard_snapshot_json),
        },
        {
            "item": "runtime_effective_mode_consistent",
            "status": "pass" if effective_mode == str(snapshot.get("effective_mode", "disabled")) else "fail",
            "details": f"runtime={effective_mode}, snapshot={snapshot.get('effective_mode')}",
        },
        {
            "item": "runtime_freshness_slo_pass",
            "status": "pass" if is_fresh else "fail",
            "details": f"slo_minutes={args.freshness_slo_minutes}",
        },
        {
            "item": "ci_contract_check_pass",
            "status": "pass" if steps[2]["ok"] else "fail",
            "details": "validate_valence_canary_snapshot.py",
        },
        {
            "item": "alerts_pipeline_connected",
            "status": "pass" if "alerts_count" in alerts else "fail",
            "details": str(args.alerts_json),
        },
    ]

    now = datetime.now(timezone.utc)
    canary_latest = _parse_utc(canary_state.get("latest_check_utc"))
    snapshot_generated = _parse_utc(snapshot.get("generated_at_utc"))
    lag_seconds = None
    if canary_latest is not None and snapshot_generated is not None:
        lag_seconds = (snapshot_generated - canary_latest).total_seconds()

    summary = {
        "experiment_id": f"e2-17-canary-observability-drill-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "freshness_slo_minutes": args.freshness_slo_minutes,
        "scheduler_steps_ok": all(step["ok"] for step in steps[:2]),
        "contract_check_ok": steps[2]["ok"],
        "effective_mode": effective_mode,
        "snapshot_effective_mode": snapshot.get("effective_mode"),
        "runtime_is_fresh": bool(is_fresh),
        "alerts_count": int(alerts.get("alerts_count", 0)),
        "snapshot_lag_seconds_from_canary_check": lag_seconds,
        "signoff_pass_count": sum(1 for item in checks if item["status"] == "pass"),
        "signoff_total": len(checks),
        "decision": "operational_signoff_ready" if all(item["status"] == "pass" for item in checks) else "operational_signoff_blocked",
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation-report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(out / "signoff-checklist.csv", checks)
    (out / "scheduler-run-log.json").write_text(json.dumps({"steps": steps}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "runtime-endpoint-response.json").write_text(json.dumps(runtime_response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.17 End-to-End Canary Observability Drill",
                "",
                f"- Decision: `{summary['decision']}`",
                f"- Sign-off: `{summary['signoff_pass_count']}/{summary['signoff_total']}`",
                f"- Runtime mode: `{effective_mode}`",
                f"- Snapshot fresh: `{is_fresh}`",
                f"- Alerts count: `{summary['alerts_count']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.17 end-to-end canary observability drill")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go"),
    )
    parser.add_argument(
        "--policy-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/scoped-policy.json"
        ),
    )
    parser.add_argument(
        "--canary-state-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/canary-state.json"
        ),
    )
    parser.add_argument(
        "--dashboard-snapshot-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/dashboard-snapshot.json"
        ),
    )
    parser.add_argument(
        "--alerts-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/alerts.json"
        ),
    )
    parser.add_argument("--freshness-slo-minutes", type=int, default=120)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-17-end-to-end-canary-observability"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
