#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
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


def run(args: argparse.Namespace) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date()
    window_start = date.fromisoformat(args.window_start_date)
    window_end = date.fromisoformat(args.window_end_date)
    audit_due_date = date.fromisoformat(args.audit_due_date)

    if today < window_end:
        decision = "blocked_until_window_close"
        status = "blocked"
        reason = (
            f"First steady-state window is still open: {window_start.isoformat()} .. {window_end.isoformat()} (UTC). "
            f"Real audit can be executed on/after {audit_due_date.isoformat()}."
        )
    else:
        decision = "audit_window_closed_execute_now"
        status = "ready"
        reason = "Window closed; run factual SLA/OLA compliance audit."

    report = {
        "experiment_id": f"e2-24-first-weekly-cycle-audit-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "window": {
            "week_utc": args.week_label,
            "start_date": window_start.isoformat(),
            "end_date": window_end.isoformat(),
            "audit_due_date": audit_due_date.isoformat(),
        },
        "status": status,
        "decision": decision,
        "reason": reason,
    }

    checklist_rows = [
        {"item": "weekly_summary_present", "status": "pending", "details": f"expected after {window_end.isoformat()}"},
        {"item": "handoff_checklist_present", "status": "pending", "details": f"expected after {window_end.isoformat()}"},
        {"item": "sla_ola_compliance_calculated", "status": "pending", "details": "requires factual timestamps"},
        {"item": "post_kickoff_adjustments_recorded", "status": "pending", "details": "finalized after factual audit"},
    ]

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(out / "audit-checklist-template.csv", checklist_rows)
    (out / "post-kickoff-adjustments.md").write_text(
        "\n".join(
            [
                "# E2.24 Post-Kickoff Adjustments",
                "",
                f"- Current status: `{status}`",
                f"- Decision: `{decision}`",
                f"- Reason: {reason}",
                "",
                "## Placeholder",
                "",
                "Factual adjustments will be recorded after first weekly window closes.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.24 First Weekly Cycle Audit",
                "",
                f"- Status: `{status}`",
                f"- Decision: `{decision}`",
                f"- Window: `{window_start.isoformat()} .. {window_end.isoformat()}` (UTC)",
                f"- Audit due date: `{audit_due_date.isoformat()}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.24 first weekly cycle audit (temporal gate aware)")
    parser.add_argument("--week-label", type=str, default="2026-W14")
    parser.add_argument("--window-start-date", type=str, default="2026-03-30")
    parser.add_argument("--window-end-date", type=str, default="2026-04-05")
    parser.add_argument("--audit-due-date", type=str, default="2026-04-06")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-24-first-weekly-cycle-audit"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
