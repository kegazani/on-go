#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
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


def _resolve_runtime_modes(
    policy_path: Path,
    baseline_canary_state_path: Path,
    drill_canary_state_path: Path,
) -> dict[str, Any]:
    api_src = Path("/Users/kgz/Desktop/p/on-go/services/inference-api/src")
    if str(api_src) not in sys.path:
        sys.path.insert(0, str(api_src))

    from inference_api.api import _effective_mode, _load_canary_state, _load_valence_policy  # type: ignore

    policy, _ = _load_valence_policy(str(policy_path))
    baseline_state, baseline_loaded = _load_canary_state(str(baseline_canary_state_path))
    drill_state, drill_loaded = _load_canary_state(str(drill_canary_state_path))
    return {
        "policy_mode": policy.get("mode", "disabled"),
        "baseline_canary_loaded": baseline_loaded,
        "drill_canary_loaded": drill_loaded,
        "baseline_effective_mode": _effective_mode(policy=policy, canary_state=baseline_state),
        "drill_effective_mode": _effective_mode(policy=policy, canary_state=drill_state),
        "baseline_auto_disable": bool(baseline_state.get("auto_disable", False)),
        "drill_auto_disable": bool(drill_state.get("auto_disable", False)),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    policy = json.loads(args.policy_json.read_text(encoding="utf-8"))
    rollback_triggers = _read_csv(args.rollback_triggers_csv)
    base_metrics = _read_csv(args.shadow_cycle_metrics_csv)
    if not base_metrics:
        raise ValueError("shadow_cycle_metrics_csv is empty")

    drill_metrics: list[dict[str, Any]] = []
    for row in base_metrics:
        drill_metrics.append(
            {
                "cycle": int(row["cycle"]),
                "wesad_to_grex_macro_f1": float(row["wesad_to_grex_macro_f1"]),
                "grex_to_wesad_macro_f1": float(row["grex_to_wesad_macro_f1"]),
                "unknown_rate_after_gate": float(row["unknown_rate_after_gate"]),
                "prediction_volume_daily": float(row["prediction_volume_daily"]),
            }
        )

    # Forced rollback drill on last cycle: violate multiple rollback conditions.
    last = drill_metrics[-1]
    last["wesad_to_grex_macro_f1"] = 0.300000
    last["unknown_rate_after_gate"] = 0.560000
    last["prediction_volume_daily"] = 14.0

    trigger_results: list[dict[str, Any]] = []
    alerts: list[str] = []
    auto_disable = False

    for row in drill_metrics:
        for trigger in rollback_triggers:
            metric, cmp_op, threshold = _parse_condition(trigger["condition"])
            value = float(row[metric])
            fired = _fire(value=value, cmp_op=cmp_op, threshold=threshold)
            trigger_results.append(
                {
                    "cycle": row["cycle"],
                    "trigger": trigger["trigger"],
                    "metric": metric,
                    "value": value,
                    "condition": f"{metric} {cmp_op} {threshold}",
                    "fired": fired,
                    "action": trigger["action"] if fired else "none",
                }
            )
            if fired:
                auto_disable = True
                alerts.append(
                    f"Cycle {row['cycle']}: trigger `{trigger['trigger']}` fired ({metric}={value:.6f}, condition `{cmp_op} {threshold}`)."
                )

    now = datetime.now(timezone.utc)
    canary_state_drill = {
        "auto_disable": auto_disable,
        "effective_mode_override": "disabled" if auto_disable else None,
        "latest_check_utc": now.isoformat(),
        "next_check_utc": (now + timedelta(minutes=args.check_interval_minutes)).isoformat(),
        "check_interval_minutes": args.check_interval_minutes,
        "alerts": alerts,
        "drill_mode": True,
        "source_artifacts": {
            "policy_json": str(args.policy_json),
            "shadow_cycle_metrics_csv": str(args.shadow_cycle_metrics_csv),
            "rollback_triggers_csv": str(args.rollback_triggers_csv),
        },
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "drill-shadow-cycle-metrics.csv", drill_metrics)
    _write_csv(out / "drill-trigger-results.csv", trigger_results)
    (out / "drill-canary-state.json").write_text(
        json.dumps(canary_state_drill, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "drill-alerts.json").write_text(
        json.dumps({"alerts": alerts, "alerts_count": len(alerts), "generated_at_utc": now.isoformat()}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    runtime_confirmation = _resolve_runtime_modes(
        policy_path=args.policy_json,
        baseline_canary_state_path=args.baseline_canary_state_json,
        drill_canary_state_path=out / "drill-canary-state.json",
    )
    (out / "runtime-drill-confirmation.json").write_text(
        json.dumps(runtime_confirmation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    recovery = {
        "objective": "Return from forced auto-disable to internal_scoped safely.",
        "sla": {
            "detect_trigger_minutes": 5,
            "operator_ack_minutes": 10,
            "rollback_execution_minutes": 5,
            "stability_observation_minutes": 60,
            "target_rto_minutes": 80,
        },
        "steps": [
            "Acknowledge alert and freeze user-facing channels (already blocked by policy).",
            "Identify violated KPI(s) and verify trigger authenticity.",
            "Switch canary state to auto_disable=true (if not already) and keep effective_mode_override=disabled.",
            "Run root-cause checks on data drift/model availability.",
            "After KPI recovery across at least 2 checks, clear auto_disable and remove effective override.",
            "Re-enable internal_scoped mode and monitor one full check interval.",
        ],
    }
    (out / "recovery-sla.json").write_text(json.dumps(recovery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "experiment_id": f"e2-14-valence-canary-drill-{now.strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": now.isoformat(),
        "policy_mode": policy.get("mode", "disabled"),
        "forced_trigger_cycles": sorted({int(item["cycle"]) for item in trigger_results if item["fired"]}),
        "triggered_count": sum(1 for item in trigger_results if item["fired"]),
        "auto_disable_after_drill": auto_disable,
        "runtime_confirmation": runtime_confirmation,
        "decision": "rollback_path_confirmed" if auto_disable and runtime_confirmation["drill_effective_mode"] == "disabled" else "rollback_path_failed",
    }
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.14 Canary Drill and Rollback Simulation",
                "",
                f"- Policy mode: `{policy.get('mode', 'disabled')}`",
                f"- Forced trigger count: `{report['triggered_count']}`",
                f"- Auto-disable after drill: `{auto_disable}`",
                f"- Runtime baseline effective mode: `{runtime_confirmation['baseline_effective_mode']}`",
                f"- Runtime drill effective mode: `{runtime_confirmation['drill_effective_mode']}`",
                f"- Decision: `{report['decision']}`",
                "",
                "## Recovery SLA",
                "",
                "- Target RTO: `80 min`.",
                "- Recovery requires two consecutive stable checks before returning to `internal_scoped`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.14 canary rollback drill")
    parser.add_argument(
        "--policy-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/scoped-policy.json"
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
        "--shadow-cycle-metrics-csv",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-12-valence-shadow-cycle-evaluation/shadow-cycle-metrics.csv"
        ),
    )
    parser.add_argument(
        "--baseline-canary-state-json",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/canary-state.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill"),
    )
    parser.add_argument("--check-interval-minutes", type=int, default=60)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
