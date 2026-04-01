#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date, datetime, time, timedelta, timezone
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


def _parse_md_value(text: str, label: str) -> str | None:
    pattern = re.compile(rf"^- {re.escape(label)}: `([^`]+)`\s*$", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1) if match else None


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if value is None or value in {"<timestamp>", "n/a", "N/A"}:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_checklist(path: Path) -> tuple[list[dict[str, str]], dict[str, bool]]:
    if not path.exists():
        return [], {"exists": False, "all_pass": False}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    statuses = [(row.get("status") or "").strip().lower() for row in rows]
    all_pass = bool(rows) and all(status == "pass" for status in statuses)
    return rows, {"exists": True, "all_pass": all_pass}


def run(args: argparse.Namespace) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date()
    window_start = date.fromisoformat(args.window_start_date)
    window_end = date.fromisoformat(args.window_end_date)
    audit_due_date = date.fromisoformat(args.audit_due_date)

    summary_path = args.weekly_summary_path
    checklist_path = args.handoff_checklist_path

    checklist_rows, checklist_meta = _read_checklist(checklist_path)
    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""

    prepared_at = _parse_iso_timestamp(_parse_md_value(summary_text, "Prepared at (UTC)"))
    triage_started_at = _parse_iso_timestamp(_parse_md_value(summary_text, "Triage started at (UTC)"))
    triage_completed_at = _parse_iso_timestamp(_parse_md_value(summary_text, "Triage completed at (UTC)"))
    handoff_completed_at = _parse_iso_timestamp(_parse_md_value(summary_text, "Handoff completed at (UTC)"))
    weekly_decision = _parse_md_value(summary_text, "Weekly decision")
    sla_ola_status = _parse_md_value(summary_text, "SLA/OLA status")

    ola_summary_deadline = datetime.combine(window_end, time(hour=18, minute=0, tzinfo=timezone.utc))
    ola_handoff_deadline = datetime.combine(window_end, time(hour=20, minute=0, tzinfo=timezone.utc))

    temporal_ready = today >= audit_due_date
    has_inputs = summary_path.exists() and checklist_meta["exists"]
    has_required_timestamps = all(
        ts is not None for ts in [prepared_at, triage_started_at, triage_completed_at, handoff_completed_at]
    )

    checks = [
        {
            "item": "temporal_gate_open",
            "status": "pass" if temporal_ready else "blocked",
            "details": f"today_utc={today.isoformat()}, audit_due_date={audit_due_date.isoformat()}",
        },
        {
            "item": "weekly_summary_present",
            "status": "pass" if summary_path.exists() else "blocked",
            "details": str(summary_path),
        },
        {
            "item": "handoff_checklist_present",
            "status": "pass" if checklist_meta["exists"] else "blocked",
            "details": str(checklist_path),
        },
        {
            "item": "handoff_checklist_all_pass",
            "status": "pass" if checklist_meta["all_pass"] else "warn",
            "details": f"rows={len(checklist_rows)}",
        },
        {
            "item": "summary_timestamps_complete",
            "status": "pass" if has_required_timestamps else "warn",
            "details": "prepared/triage_started/triage_completed/handoff_completed",
        },
    ]

    decision: str
    status: str
    reason: str

    if not temporal_ready:
        status = "blocked"
        decision = "blocked_until_audit_due_date"
        reason = (
            "Factual weekly-cycle audit is date-blocked: "
            f"window={window_start.isoformat()}..{window_end.isoformat()} (UTC), "
            f"audit can run on/after {audit_due_date.isoformat()}."
        )
    elif not has_inputs:
        status = "blocked"
        decision = "blocked_missing_weekly_inputs"
        reason = "Weekly summary or handoff checklist not found for factual compliance audit."
    else:
        chronology_ok = bool(
            prepared_at
            and triage_started_at
            and triage_completed_at
            and handoff_completed_at
            and triage_started_at <= triage_completed_at <= handoff_completed_at
        )
        summary_deadline_ok = bool(prepared_at and prepared_at <= ola_summary_deadline)
        handoff_deadline_ok = bool(handoff_completed_at and handoff_completed_at <= ola_handoff_deadline)
        checklist_ok = checklist_meta["all_pass"]

        checks.extend(
            [
                {
                    "item": "timestamp_chronology_valid",
                    "status": "pass" if chronology_ok else "fail",
                    "details": "triage_started <= triage_completed <= handoff_completed",
                },
                {
                    "item": "ola_summary_deadline_met",
                    "status": "pass" if summary_deadline_ok else "fail",
                    "details": f"deadline={ola_summary_deadline.isoformat()}",
                },
                {
                    "item": "ola_handoff_deadline_met",
                    "status": "pass" if handoff_deadline_ok else "fail",
                    "details": f"deadline={ola_handoff_deadline.isoformat()}",
                },
            ]
        )

        failed = [c for c in checks if c["status"] in {"fail", "blocked"}]
        warned = [c for c in checks if c["status"] == "warn"]
        if failed:
            status = "fail"
            decision = "weekly_compliance_fail"
            reason = f"Compliance checks failed: {len(failed)} issue(s)."
        elif warned:
            status = "warn"
            decision = "weekly_compliance_warn"
            reason = f"Compliance checks passed with warnings: {len(warned)} warning(s)."
        else:
            status = "pass"
            decision = "weekly_compliance_pass"
            reason = "All factual weekly compliance checks passed."

    report = {
        "experiment_id": f"e2-25-factual-weekly-cycle-audit-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "window": {
            "week_utc": args.week_label,
            "start_date": window_start.isoformat(),
            "end_date": window_end.isoformat(),
            "audit_due_date": audit_due_date.isoformat(),
        },
        "inputs": {
            "weekly_summary_path": str(summary_path),
            "handoff_checklist_path": str(checklist_path),
            "weekly_summary_exists": summary_path.exists(),
            "handoff_checklist_exists": checklist_meta["exists"],
        },
        "status": status,
        "decision": decision,
        "reason": reason,
        "weekly_decision": weekly_decision,
        "weekly_sla_ola_status": sla_ola_status,
        "parsed_timestamps_utc": {
            "prepared_at_utc": prepared_at.isoformat() if prepared_at else None,
            "triage_started_at_utc": triage_started_at.isoformat() if triage_started_at else None,
            "triage_completed_at_utc": triage_completed_at.isoformat() if triage_completed_at else None,
            "handoff_completed_at_utc": handoff_completed_at.isoformat() if handoff_completed_at else None,
        },
        "checks": checks,
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(out / "audit-checklist.csv", checks)
    (out / "post-kickoff-adjustments.md").write_text(
        "\n".join(
            [
                "# E2.25 Post-Kickoff Adjustments",
                "",
                f"- Status: `{status}`",
                f"- Decision: `{decision}`",
                f"- Reason: {reason}",
                "",
                "## Actions",
                "",
                "- Fill weekly summary + handoff checklist inputs when temporal gate is open.",
                "- Re-run E2.25 script and update compliance status with factual timestamps.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.25 Execute Factual First Weekly Cycle Audit",
                "",
                f"- Status: `{status}`",
                f"- Decision: `{decision}`",
                f"- Window: `{window_start.isoformat()} .. {window_end.isoformat()}` (UTC)",
                f"- Audit due date: `{audit_due_date.isoformat()}`",
                f"- Weekly summary exists: `{summary_path.exists()}`",
                f"- Handoff checklist exists: `{checklist_meta['exists']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.25 factual first weekly cycle audit")
    parser.add_argument("--week-label", type=str, default="2026-W14")
    parser.add_argument("--window-start-date", type=str, default="2026-03-30")
    parser.add_argument("--window-end-date", type=str, default="2026-04-05")
    parser.add_argument("--audit-due-date", type=str, default="2026-04-06")
    parser.add_argument(
        "--weekly-summary-path",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit/weekly-summary.md"
        ),
    )
    parser.add_argument(
        "--handoff-checklist-path",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit/handoff-checklist.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
