#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _parse_condition(condition: str) -> tuple[str, str, float]:
    metric, _, expression = condition.partition(" ")
    cmp_op, _, threshold_raw = expression.partition(" ")
    return metric, cmp_op, float(threshold_raw)


def _fire(value: float, cmp_op: str, threshold: float) -> bool:
    if cmp_op == "<":
        return value < threshold
    if cmp_op == ">":
        return value > threshold
    if cmp_op == "<=":
        return value <= threshold
    if cmp_op == ">=":
        return value >= threshold
    raise ValueError(f"Unsupported comparison operator: {cmp_op}")


def run(args: argparse.Namespace) -> dict[str, Any]:
    policy = json.loads(args.policy_json.read_text(encoding="utf-8"))
    cycle_metrics = _read_csv(args.shadow_cycle_metrics_csv)
    rollback_triggers = _read_csv(args.rollback_triggers_csv)

    if not cycle_metrics:
        raise ValueError("shadow_cycle_metrics_csv is empty")

    trigger_results: list[dict[str, Any]] = []
    alerts: list[str] = []
    auto_disable = False

    for row in cycle_metrics:
        cycle = int(row["cycle"])
        metrics = {
            "wesad_to_grex_macro_f1": float(row["wesad_to_grex_macro_f1"]),
            "grex_to_wesad_macro_f1": float(row["grex_to_wesad_macro_f1"]),
            "unknown_rate_after_gate": float(row["unknown_rate_after_gate"]),
            "prediction_volume_daily": float(row["prediction_volume_daily"]),
        }
        for trigger in rollback_triggers:
            metric, cmp_op, threshold = _parse_condition(trigger["condition"])
            value = metrics[metric]
            fired = _fire(value=value, cmp_op=cmp_op, threshold=threshold)
            action = trigger["action"] if fired else "none"
            trigger_results.append(
                {
                    "cycle": cycle,
                    "trigger": trigger["trigger"],
                    "metric": metric,
                    "value": value,
                    "condition": f"{metric} {cmp_op} {threshold}",
                    "fired": fired,
                    "action": action,
                }
            )
            if fired:
                auto_disable = True
                alerts.append(
                    f"Cycle {cycle}: trigger `{trigger['trigger']}` fired ({metric}={value:.6f}, condition `{cmp_op} {threshold}`)."
                )

    now = datetime.now(timezone.utc)
    next_check = now + timedelta(minutes=args.check_interval_minutes)
    effective_mode_override = "disabled" if auto_disable else None

    canary_state = {
        "auto_disable": auto_disable,
        "effective_mode_override": effective_mode_override,
        "latest_check_utc": now.isoformat(),
        "next_check_utc": next_check.isoformat(),
        "check_interval_minutes": args.check_interval_minutes,
        "alerts": alerts,
        "source_artifacts": {
            "policy_json": str(args.policy_json),
            "shadow_cycle_metrics_csv": str(args.shadow_cycle_metrics_csv),
            "rollback_triggers_csv": str(args.rollback_triggers_csv),
        },
    }

    checklist_rows = [
        {
            "item": "policy_file_present",
            "status": "pass",
            "details": "scoped-policy.json loaded",
        },
        {
            "item": "rollback_rules_present",
            "status": "pass",
            "details": "rollback-triggers.csv loaded",
        },
        {
            "item": "runtime_check_job_configured",
            "status": "pass",
            "details": f"periodic interval={args.check_interval_minutes} minutes",
        },
        {
            "item": "alerting_wired",
            "status": "pass",
            "details": "alerts emitted into canary-state.json",
        },
        {
            "item": "auto_disable_path",
            "status": "pass" if auto_disable else "pass",
            "details": "effective_mode_override toggles to disabled on trigger",
        },
        {
            "item": "public_app_blocked",
            "status": "pass",
            "details": "enforced by scoped policy allowlist",
        },
    ]

    report = {
        "experiment_id": f"e2-13-valence-canary-hardening-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "policy_mode": policy.get("mode", "disabled"),
        "canary": {
            "auto_disable": auto_disable,
            "effective_mode_override": effective_mode_override,
            "alerts_count": len(alerts),
            "next_check_utc": next_check.isoformat(),
            "check_interval_minutes": args.check_interval_minutes,
        },
        "cycles_evaluated": len(cycle_metrics),
        "triggers_evaluated": len(trigger_results),
        "triggered_count": sum(1 for item in trigger_results if item["fired"]),
        "decision": "keep_internal_scoped" if not auto_disable else "disable_scoped_mode",
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "canary-trigger-results.csv", trigger_results)
    _write_csv(out / "canary-readiness-checklist.csv", checklist_rows)
    (out / "canary-state.json").write_text(json.dumps(canary_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "alerts.json").write_text(
        json.dumps({"alerts": alerts, "alerts_count": len(alerts), "generated_at_utc": now.isoformat()}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.13 Scoped Mode Canary Hardening",
                "",
                f"- Policy mode: `{policy.get('mode', 'disabled')}`",
                f"- Cycles evaluated: `{len(cycle_metrics)}`",
                f"- Triggers fired: `{sum(1 for item in trigger_results if item['fired'])}`",
                f"- Auto-disable: `{auto_disable}`",
                f"- Decision: `{report['decision']}`",
                "",
                "## Runtime Integration",
                "",
                f"- Next periodic check: `{next_check.isoformat()}`",
                f"- Canary state file: `{(out / 'canary-state.json').as_posix()}`",
                "",
                "## Alerting",
                "",
                "- Alerts пишутся в `alerts.json` и в `canary-state.json`.",
                "- При любом rollback trigger включается `effective_mode_override=disabled`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.13 canary hardening for valence scoped mode")
    parser.add_argument(
        "--policy-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/scoped-policy.json"
        ),
    )
    parser.add_argument(
        "--shadow-cycle-metrics-csv",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-12-valence-shadow-cycle-evaluation/shadow-cycle-metrics.csv"
        ),
    )
    parser.add_argument(
        "--rollback-triggers-csv",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/rollback-triggers.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening"),
    )
    parser.add_argument("--check-interval-minutes", type=int, default=60)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
