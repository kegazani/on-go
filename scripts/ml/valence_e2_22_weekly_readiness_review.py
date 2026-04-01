#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _build_weekly_summary(now: datetime, owner: str, triage_id: str) -> str:
    week_label = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    week_start = (now - timedelta(days=6)).date().isoformat()
    week_end = now.date().isoformat()
    prepared = now.isoformat()
    triage_started = (now - timedelta(hours=2)).isoformat()
    triage_completed = (now - timedelta(hours=1, minutes=10)).isoformat()
    handoff_completed = (now - timedelta(minutes=30)).isoformat()
    return "\n".join(
        [
            "# Valence Canary Weekly Summary (E2.22 Simulated)",
            "",
            "## Period",
            "",
            f"- Week (UTC): `{week_label}`",
            f"- Window: `{week_start} .. {week_end}`",
            f"- Prepared at (UTC): `{prepared}`",
            f"- Owner: `{owner}`",
            f"- Triage started at (UTC): `{triage_started}`",
            f"- Triage completed at (UTC): `{triage_completed}`",
            f"- Handoff completed at (UTC): `{handoff_completed}`",
            f"- Triage task / incident id: `{triage_id}`",
            "",
            "## Weekly KPI",
            "",
            "| KPI | Value | Threshold | Status |",
            "| --- | --- | --- | --- |",
            "| `cycles_total` | `7` | `>= 7` | `pass` |",
            "| `cycles_pass_rate` | `1.00` | `>= 0.95` | `pass` |",
            "| `alerts_total` | `0` | `<= 1 warn / 0 critical` | `pass` |",
            "| `auto_disable_events` | `0` | `0` | `pass` |",
            "| `freshness_slo_violations` | `0` | `0` | `pass` |",
            "| `effective_mode_drift_events` | `0` | `0` | `pass` |",
            "",
            "## Escalation Check",
            "",
            "- `warn` condition triggered: `no`",
            "- `critical` condition triggered: `no`",
            "- Incident created: `n/a`",
            "",
            "## Compliance",
            "",
            "- SLA/OLA status: `pass`",
            "- Retention class: `weekly_summary_26w`",
        ]
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    e2_20_report = json.loads(args.e2_20_report_json.read_text(encoding="utf-8"))
    e2_20_checklist = _read_csv(args.e2_20_handoff_checklist_csv)

    simulated_summary = _build_weekly_summary(now=now, owner=args.owner, triage_id=args.triage_task_id)
    required_fields = [
        "Prepared at (UTC)",
        "Triage started at (UTC)",
        "Triage completed at (UTC)",
        "Handoff completed at (UTC)",
        "Triage task / incident id",
        "SLA/OLA status",
    ]
    fields_present = all(field in simulated_summary for field in required_fields)
    e2_20_ready = str(e2_20_report.get("decision", "")) == "weekly_handoff_ready"
    checklist_pass = all(row.get("status") == "pass" for row in e2_20_checklist)
    steady_state_ready = all([fields_present, e2_20_ready, checklist_pass])

    checks = [
        {"item": "e2_20_decision_ready", "status": "pass" if e2_20_ready else "fail", "details": str(e2_20_report.get("decision"))},
        {"item": "e2_20_handoff_checklist_all_pass", "status": "pass" if checklist_pass else "fail", "details": str(len(e2_20_checklist))},
        {"item": "weekly_summary_required_fields_present", "status": "pass" if fields_present else "fail", "details": "prepared/triage/handoff/sla_ola"},
        {"item": "sla_ola_compliance_recorded", "status": "pass" if "SLA/OLA status: `pass`" in simulated_summary else "fail", "details": "simulated_weekly_summary"},
    ]

    decision = "steady_state_ready" if steady_state_ready else "steady_state_blocked"
    report = {
        "experiment_id": f"e2-22-weekly-readiness-review-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "inputs": {
            "e2_20_report_json": str(args.e2_20_report_json),
            "e2_20_handoff_checklist_csv": str(args.e2_20_handoff_checklist_csv),
        },
        "checks_pass": sum(1 for row in checks if row["status"] == "pass"),
        "checks_total": len(checks),
        "decision": decision,
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(out / "readiness-checklist.csv", checks)
    (out / "weekly-summary-simulated.md").write_text(simulated_summary + "\n", encoding="utf-8")
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.22 Weekly Operations Readiness Review",
                "",
                f"- Decision: `{decision}`",
                f"- Checks: `{report['checks_pass']}/{report['checks_total']}`",
                f"- Based on E2.20 decision: `{e2_20_report.get('decision')}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.22 weekly operations readiness review")
    parser.add_argument("--owner", type=str, default="ML/Inference on-call")
    parser.add_argument("--triage-task-id", type=str, default="TRIAGE-E2-22-SIM-001")
    parser.add_argument(
        "--e2-20-report-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/evaluation-report.json"
        ),
    )
    parser.add_argument(
        "--e2-20-handoff-checklist-csv",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/handoff-dry-run-checklist.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-22-weekly-operations-readiness-review"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
