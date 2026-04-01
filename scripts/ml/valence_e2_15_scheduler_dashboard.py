#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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


def _require_keys(obj: dict[str, Any], keys: list[str]) -> list[str]:
    missing: list[str] = []
    for key in keys:
        if key not in obj:
            missing.append(key)
    return missing


def run(args: argparse.Namespace) -> dict[str, Any]:
    policy = json.loads(args.policy_json.read_text(encoding="utf-8"))
    canary_state = json.loads(args.canary_state_json.read_text(encoding="utf-8"))
    canary_eval = json.loads(args.canary_eval_json.read_text(encoding="utf-8"))
    canary_alerts = json.loads(args.canary_alerts_json.read_text(encoding="utf-8"))

    policy_mode = str(policy.get("mode", "disabled"))
    auto_disable = bool(canary_state.get("auto_disable", False))
    override = canary_state.get("effective_mode_override")
    effective_mode = str(override) if isinstance(override, str) else policy_mode
    if auto_disable and not isinstance(override, str):
        effective_mode = "disabled"

    alerts = canary_state.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []
    alerts = [str(item) for item in alerts]

    status = "healthy"
    if effective_mode == "disabled":
        status = "disabled"
    elif alerts:
        status = "degraded"

    now = datetime.now(timezone.utc)
    snapshot = {
        "snapshot_id": f"valence-canary-snapshot-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "policy_mode": policy_mode,
        "effective_mode": effective_mode,
        "auto_disable": auto_disable,
        "status": status,
        "alerts_count": int(canary_alerts.get("alerts_count", len(alerts))),
        "latest_check_utc": str(canary_state.get("latest_check_utc", now.isoformat())),
        "next_check_utc": str(canary_state.get("next_check_utc", now.isoformat())),
        "check_interval_minutes": int(canary_state.get("check_interval_minutes", 60)),
        "alerts": alerts,
        "kpi_rollup": {
            "cycles_evaluated": int(canary_eval.get("cycles_evaluated", 0)),
            "triggers_evaluated": int(canary_eval.get("triggers_evaluated", 0)),
            "triggered_count": int(canary_eval.get("triggered_count", 0)),
        },
    }

    required_snapshot_keys = [
        "snapshot_id",
        "generated_at_utc",
        "policy_mode",
        "effective_mode",
        "auto_disable",
        "status",
        "alerts_count",
        "latest_check_utc",
        "next_check_utc",
        "check_interval_minutes",
        "alerts",
    ]
    missing_snapshot = _require_keys(snapshot, required_snapshot_keys)

    scheduler_spec = {
        "scheduler_id": "valence-canary-check",
        "description": "Periodic execution of E2.13 canary check with dashboard snapshot refresh.",
        "modes": [
            {
                "kind": "github_actions",
                "workflow": ".github/workflows/valence-canary-check.yml",
                "interval_minutes": 60,
            },
            {
                "kind": "cron",
                "spec_file": "infra/ops/valence-canary/cron/valence-canary-check.cron",
                "interval_minutes": 60,
            },
            {
                "kind": "systemd",
                "service_file": "infra/ops/valence-canary/systemd/valence-canary-check.service",
                "timer_file": "infra/ops/valence-canary/systemd/valence-canary-check.timer",
                "interval_minutes": 60,
            },
        ],
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "dashboard-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "scheduler-spec.json").write_text(json.dumps(scheduler_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checklist = [
        {
            "item": "github_actions_schedule",
            "status": "pass" if args.github_workflow.exists() else "fail",
            "details": str(args.github_workflow),
        },
        {
            "item": "cron_spec_present",
            "status": "pass" if args.cron_spec.exists() else "fail",
            "details": str(args.cron_spec),
        },
        {
            "item": "systemd_service_present",
            "status": "pass" if args.systemd_service.exists() else "fail",
            "details": str(args.systemd_service),
        },
        {
            "item": "systemd_timer_present",
            "status": "pass" if args.systemd_timer.exists() else "fail",
            "details": str(args.systemd_timer),
        },
        {
            "item": "dashboard_snapshot_contract_keys",
            "status": "pass" if not missing_snapshot else "fail",
            "details": "missing=" + ",".join(missing_snapshot) if missing_snapshot else "all required keys present",
        },
        {
            "item": "alerts_source_connected",
            "status": "pass" if "alerts_count" in canary_alerts else "fail",
            "details": str(args.canary_alerts_json),
        },
    ]
    _write_csv(out / "acceptance-checklist.csv", checklist)

    overall_pass = all(item["status"] == "pass" for item in checklist)
    report = {
        "experiment_id": f"e2-15-valence-scheduler-dashboard-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "overall_status": "ready" if overall_pass else "not_ready",
        "policy_mode": policy_mode,
        "effective_mode": effective_mode,
        "auto_disable": auto_disable,
        "alerts_count": int(snapshot["alerts_count"]),
        "acceptance_pass_count": sum(1 for item in checklist if item["status"] == "pass"),
        "acceptance_total": len(checklist),
    }
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.15 Canary Scheduler and Dashboard Contract",
                "",
                f"- Overall status: `{report['overall_status']}`",
                f"- Effective mode: `{effective_mode}`",
                f"- Auto-disable: `{auto_disable}`",
                f"- Alerts count: `{snapshot['alerts_count']}`",
                f"- Acceptance: `{report['acceptance_pass_count']}/{report['acceptance_total']}`",
                "",
                "## Outputs",
                "",
                "- `dashboard-snapshot.json`",
                "- `scheduler-spec.json`",
                "- `acceptance-checklist.csv`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.15 scheduler wiring and dashboard contract")
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
        "--canary-eval-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/evaluation-report.json"
        ),
    )
    parser.add_argument(
        "--canary-alerts-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/alerts.json"
        ),
    )
    parser.add_argument(
        "--github-workflow",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/.github/workflows/valence-canary-check.yml"),
    )
    parser.add_argument(
        "--cron-spec",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/infra/ops/valence-canary/cron/valence-canary-check.cron"),
    )
    parser.add_argument(
        "--systemd-service",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/infra/ops/valence-canary/systemd/valence-canary-check.service"),
    )
    parser.add_argument(
        "--systemd-timer",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/infra/ops/valence-canary/systemd/valence-canary-check.timer"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
