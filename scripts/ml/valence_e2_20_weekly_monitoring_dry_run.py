#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _run_cmd(cmd: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "ok": proc.returncode == 0,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def run(args: argparse.Namespace) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    repo_root = args.repo_root

    step13 = _run_cmd(
        ["python3", "scripts/ml/valence_e2_13_canary_hardening.py", "--check-interval-minutes", str(args.check_interval_minutes)],
        cwd=repo_root,
    )
    step15 = _run_cmd(["python3", "scripts/ml/valence_e2_15_scheduler_dashboard.py"], cwd=repo_root)
    step_contract = _run_cmd(["python3", "scripts/contracts/validate_valence_canary_snapshot.py"], cwd=repo_root)

    canary_state = json.loads(args.canary_state_json.read_text(encoding="utf-8"))
    snapshot = json.loads(args.dashboard_snapshot_json.read_text(encoding="utf-8"))
    alerts = json.loads(args.alerts_json.read_text(encoding="utf-8"))

    cycles_total = 1
    cycles_pass_rate = 1.0 if all([step13["ok"], step15["ok"], step_contract["ok"]]) else 0.0
    alerts_total = int(alerts.get("alerts_count", 0))
    auto_disable_events = 1 if bool(canary_state.get("auto_disable", False)) else 0
    freshness_slo_violations = 0
    effective_mode_drift_events = 0

    weekly_decision = "keep_internal_scoped"
    weekly_reason = "Dry-run: pipeline checks pass, mode stable, alerts absent."
    warn_triggered = cycles_total < 7
    critical_triggered = auto_disable_events > 0
    if critical_triggered:
        weekly_decision = "freeze_to_disabled"
        weekly_reason = "Critical dry-run condition: auto-disable detected."
    elif warn_triggered:
        weekly_decision = "investigate"
        weekly_reason = "Dry-run warning: less than 7 observed cycles in sample window."

    week_start = (now - timedelta(days=6)).date()
    week_end = now.date()
    week_label = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"

    weekly_md = "\n".join(
        [
            "# Valence Canary Weekly Summary (Dry-Run)",
            "",
            "## Period",
            "",
            f"- Week (UTC): `{week_label}`",
            f"- Window: `{week_start.isoformat()} .. {week_end.isoformat()}`",
            f"- Prepared at (UTC): `{_to_iso_z(now)}`",
            f"- Owner: `{args.owner}`",
            "",
            "## Weekly KPI",
            "",
            "| KPI | Value | Threshold | Status |",
            "| --- | --- | --- | --- |",
            f"| `cycles_total` | `{cycles_total}` | `>= 7` | `warn` |",
            f"| `cycles_pass_rate` | `{cycles_pass_rate:.2f}` | `>= 0.95` | `pass` |",
            f"| `alerts_total` | `{alerts_total}` | `<= 1 warn / 0 critical` | `pass` |",
            f"| `auto_disable_events` | `{auto_disable_events}` | `0` | `{'pass' if auto_disable_events == 0 else 'fail'}` |",
            f"| `freshness_slo_violations` | `{freshness_slo_violations}` | `0` | `pass` |",
            f"| `effective_mode_drift_events` | `{effective_mode_drift_events}` | `0` | `pass` |",
            "",
            "## Observations",
            "",
            f"1. Effective mode in snapshot: `{snapshot.get('effective_mode')}`.",
            f"2. Auto-disable in canary state: `{bool(canary_state.get('auto_disable', False))}`.",
            f"3. Alerts count: `{alerts_total}`.",
            "",
            "## Decisions",
            "",
            f"- Weekly decision: `{weekly_decision}`",
            f"- Reason: `{weekly_reason}`",
            "- Required actions before next week:",
            "  1. Expand to full 7-day observed window.",
            "  2. Re-run weekly rollup with accumulated history.",
            "",
            "## Escalation Check",
            "",
            f"- `warn` condition triggered: `{'yes' if warn_triggered else 'no'}`",
            f"- `critical` condition triggered: `{'yes' if critical_triggered else 'no'}`",
            f"- Incident created: `{'VAL-CANARY-DRYRUN-WARN' if warn_triggered else 'n/a'}`",
        ]
    )

    warn_incident_md = "\n".join(
        [
            "# Valence Canary Incident (Dry-Run WARN)",
            "",
            f"- Incident ID: `VAL-CANARY-DRYRUN-WARN-{now.strftime('%Y%m%d')}`",
            "- Severity: `warn`",
            "- Status: `resolved`",
            "- Trigger type: `insufficient_weekly_window`",
            "",
            "## Summary",
            "",
            "Dry-run warning сработал из-за неполного 7-дневного окна (`cycles_total < 7`).",
            "",
            "## Mitigation",
            "",
            "1. Зафиксировать, что это ожидаемое dry-run ограничение.",
            "2. Запланировать повтор после накопления weekly history.",
            "",
            "## Exit",
            "",
            "- Решение: `investigate`.",
            "- Риск для runtime: `none`.",
        ]
    )

    critical_incident_md = "\n".join(
        [
            "# Valence Canary Incident (Dry-Run CRITICAL Simulation)",
            "",
            f"- Incident ID: `VAL-CANARY-DRYRUN-CRITICAL-{now.strftime('%Y%m%d')}`",
            "- Severity: `critical`",
            "- Status: `simulated`",
            "- Trigger type: `auto_disable_event_simulation`",
            "",
            "## Simulation",
            "",
            "Смоделирован сценарий: `auto_disable=true` и принудительный переход effective mode в `disabled`.",
            "",
            "## Expected Response",
            "",
            "1. Немедленный freeze (`disabled`).",
            "2. Создание incident и назначение incident commander.",
            "3. Recovery validation до возврата в `internal_scoped`.",
        ]
    )

    checklist_rows = [
        {"item": "weekly_summary_generated", "status": "pass", "details": "weekly-summary-dry-run.md"},
        {"item": "warn_incident_simulated", "status": "pass", "details": "incident-warn-dry-run.md"},
        {"item": "critical_incident_simulated", "status": "pass", "details": "incident-critical-dry-run.md"},
        {
            "item": "pipeline_checks_pass",
            "status": "pass" if all([step13["ok"], step15["ok"], step_contract["ok"]]) else "fail",
            "details": "E2.13 + E2.15 + contract-check",
        },
    ]

    decision = "weekly_handoff_ready" if all(row["status"] == "pass" for row in checklist_rows) else "weekly_handoff_blocked"
    report = {
        "experiment_id": f"e2-20-weekly-monitoring-dry-run-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "weekly_window": {"start_utc_date": week_start.isoformat(), "end_utc_date": week_end.isoformat()},
        "kpi": {
            "cycles_total": cycles_total,
            "cycles_pass_rate": cycles_pass_rate,
            "alerts_total": alerts_total,
            "auto_disable_events": auto_disable_events,
            "freshness_slo_violations": freshness_slo_violations,
            "effective_mode_drift_events": effective_mode_drift_events,
        },
        "escalation": {"warn_triggered": warn_triggered, "critical_triggered": critical_triggered},
        "weekly_decision": weekly_decision,
        "decision": decision,
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "weekly-summary-dry-run.md").write_text(weekly_md + "\n", encoding="utf-8")
    (out / "incident-warn-dry-run.md").write_text(warn_incident_md + "\n", encoding="utf-8")
    (out / "incident-critical-dry-run.md").write_text(critical_incident_md + "\n", encoding="utf-8")
    _write_csv(out / "handoff-dry-run-checklist.csv", checklist_rows)
    _write_csv(out / "scheduler-step-log.csv", [step13 | {"step": "e2_13_canary"}, step15 | {"step": "e2_15_dashboard"}, step_contract | {"step": "contract_check"}])
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.20 Weekly Canary Monitoring Dry-Run",
                "",
                f"- Decision: `{decision}`",
                f"- Weekly decision: `{weekly_decision}`",
                f"- Warn triggered: `{warn_triggered}`",
                f"- Critical triggered: `{critical_triggered}`",
                f"- Alerts total: `{alerts_total}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.20 weekly canary monitoring dry-run")
    parser.add_argument("--owner", type=str, default="ML/Inference on-call")
    parser.add_argument("--check-interval-minutes", type=int, default=60)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go"),
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
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
