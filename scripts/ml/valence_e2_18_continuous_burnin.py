#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
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


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_fresh(generated_at_utc: object, freshness_slo_minutes: int) -> bool:
    generated = _parse_utc(generated_at_utc)
    if generated is None:
        return False
    age_minutes = (datetime.now(timezone.utc) - generated).total_seconds() / 60.0
    return age_minutes <= float(freshness_slo_minutes)


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root
    cycle_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []

    policy = json.loads(args.policy_json.read_text(encoding="utf-8"))
    policy_mode = str(policy.get("mode", "disabled"))

    for cycle in range(1, args.cycles + 1):
        step13 = _run_cmd(
            ["python3", "scripts/ml/valence_e2_13_canary_hardening.py", "--check-interval-minutes", str(args.check_interval_minutes)],
            cwd=repo_root,
        )
        step15 = _run_cmd(["python3", "scripts/ml/valence_e2_15_scheduler_dashboard.py"], cwd=repo_root)
        step_contract = _run_cmd(["python3", "scripts/contracts/validate_valence_canary_snapshot.py"], cwd=repo_root)

        step_rows.extend(
            [
                {"cycle": cycle, "step": "e2_13_canary", **step13},
                {"cycle": cycle, "step": "e2_15_dashboard", **step15},
                {"cycle": cycle, "step": "contract_check", **step_contract},
            ]
        )

        canary_state = json.loads(args.canary_state_json.read_text(encoding="utf-8"))
        snapshot = json.loads(args.dashboard_snapshot_json.read_text(encoding="utf-8"))
        alerts_json = json.loads(args.alerts_json.read_text(encoding="utf-8"))

        effective_mode = str(snapshot.get("effective_mode", "disabled"))
        auto_disable = bool(canary_state.get("auto_disable", False))
        alerts_count = int(alerts_json.get("alerts_count", 0))
        fresh = _is_fresh(snapshot.get("generated_at_utc"), args.freshness_slo_minutes)
        cycle_ok = all([step13["ok"], step15["ok"], step_contract["ok"], fresh, not auto_disable, alerts_count == 0, effective_mode == policy_mode])

        cycle_rows.append(
            {
                "cycle": cycle,
                "policy_mode": policy_mode,
                "effective_mode": effective_mode,
                "auto_disable": auto_disable,
                "alerts_count": alerts_count,
                "dashboard_fresh": fresh,
                "e2_13_ok": step13["ok"],
                "e2_15_ok": step15["ok"],
                "contract_check_ok": step_contract["ok"],
                "cycle_ok": cycle_ok,
            }
        )

        if cycle < args.cycles and args.interval_seconds > 0:
            time.sleep(args.interval_seconds)

    pass_count = sum(1 for row in cycle_rows if row["cycle_ok"])
    all_ok = pass_count == len(cycle_rows)
    decision = "burnin_passed" if all_ok else "burnin_failed"

    now = datetime.now(timezone.utc)
    report = {
        "experiment_id": f"e2-18-continuous-burnin-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "cycles": args.cycles,
        "freshness_slo_minutes": args.freshness_slo_minutes,
        "policy_mode": policy_mode,
        "pass_cycles": pass_count,
        "failed_cycles": len(cycle_rows) - pass_count,
        "decision": decision,
    }

    gate = {
        "gate_id": f"valence-burnin-gate-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "decision": decision,
        "criteria": {
            "min_cycles": args.cycles,
            "all_cycles_cycle_ok": all_ok,
            "effective_mode_constant": len({row['effective_mode'] for row in cycle_rows}) == 1,
            "alerts_zero_all_cycles": all(int(row["alerts_count"]) == 0 for row in cycle_rows),
            "auto_disable_false_all_cycles": all(not bool(row["auto_disable"]) for row in cycle_rows),
            "fresh_all_cycles": all(bool(row["dashboard_fresh"]) for row in cycle_rows),
        },
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "burnin-decision-gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(out / "burnin-cycle-summary.csv", cycle_rows)
    _write_csv(out / "burnin-step-log.csv", step_rows)
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.18 Continuous-Run Burn-In",
                "",
                f"- Cycles: `{args.cycles}`",
                f"- Pass cycles: `{pass_count}`",
                f"- Decision: `{decision}`",
                f"- Policy mode: `{policy_mode}`",
                "",
                "## Criteria",
                "",
                f"- Fresh all cycles: `{gate['criteria']['fresh_all_cycles']}`",
                f"- Alerts zero all cycles: `{gate['criteria']['alerts_zero_all_cycles']}`",
                f"- Auto-disable false all cycles: `{gate['criteria']['auto_disable_false_all_cycles']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.18 continuous-run burn-in")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--interval-seconds", type=int, default=0)
    parser.add_argument("--check-interval-minutes", type=int, default=60)
    parser.add_argument("--freshness-slo-minutes", type=int, default=120)
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
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-18-continuous-run-burnin"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
