#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


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
    sensitivity = _read_csv(args.sensitivity_csv)

    ridge_floor_035 = next(
        row for row in sensitivity if row["classifier_kind"] == "ridge_classifier" and float(row["floor"]) == 0.35
    )
    ridge_floor_040 = next(
        row for row in sensitivity if row["classifier_kind"] == "ridge_classifier" and float(row["floor"]) == 0.4
    )

    scoped_candidate = str(ridge_floor_035["bidirectional_pass"]).lower() == "true"
    default_floor_pass = str(ridge_floor_040["bidirectional_pass"]).lower() == "true"

    mode = "disabled"
    if scoped_candidate and not default_floor_pass:
        mode = "internal_scoped"
    if default_floor_pass:
        mode = "limited_production"

    policy = {
        "policy_id": f"valence-scoped-policy-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "mode": mode,
        "allowed_contexts": ["research_only", "internal_dashboard", "shadow_mode"] if mode != "disabled" else ["research_only"],
        "model": {
            "classifier_kind": "ridge_classifier",
            "trusted_floor": 0.35 if mode == "internal_scoped" else 0.40,
            "confidence_threshold": 0.70,
        },
        "direction_rules": [
            {
                "direction": "wesad_to_grex",
                "enabled": str(ridge_floor_035["wesad_to_grex_pass"]).lower() == "true" if mode == "internal_scoped" else default_floor_pass,
                "min_macro_f1": 0.35 if mode == "internal_scoped" else 0.40,
            },
            {
                "direction": "grex_to_wesad",
                "enabled": str(ridge_floor_035["grex_to_wesad_pass"]).lower() == "true" if mode == "internal_scoped" else default_floor_pass,
                "min_macro_f1": 0.35 if mode == "internal_scoped" else 0.40,
            },
        ],
        "guardrails": {
            "user_facing_claims": False,
            "risk_notifications": False,
            "auto_personalization_trigger": False,
        },
        "rollback": {
            "trigger_any": True,
            "checks": [
                {"name": "wesad_to_grex_macro_f1", "threshold": 0.32, "comparison": "lt"},
                {"name": "grex_to_wesad_macro_f1", "threshold": 0.40, "comparison": "lt"},
                {"name": "unknown_rate_after_gate", "threshold": 0.50, "comparison": "gt"},
            ],
        },
    }

    monitoring_rows = [
        {"kpi": "wesad_to_grex_macro_f1", "target": ">=0.35", "rollback_if": "<0.32"},
        {"kpi": "grex_to_wesad_macro_f1", "target": ">=0.50", "rollback_if": "<0.40"},
        {"kpi": "unknown_rate_after_gate", "target": "<=0.35", "rollback_if": ">0.50"},
        {"kpi": "prediction_volume_daily", "target": ">=100", "rollback_if": "<20"},
    ]
    rollback_rows = [
        {"trigger": "wesad_to_grex_drop", "condition": "wesad_to_grex_macro_f1 < 0.32", "action": "disable_scoped_mode"},
        {"trigger": "grex_to_wesad_drop", "condition": "grex_to_wesad_macro_f1 < 0.40", "action": "disable_scoped_mode"},
        {"trigger": "unknown_rate_spike", "condition": "unknown_rate_after_gate > 0.50", "action": "raise_threshold_and_shadow_only"},
    ]

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "scoped-policy.json").write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(out / "monitoring-kpis.csv", monitoring_rows)
    _write_csv(out / "rollback-triggers.csv", rollback_rows)

    gate = {
        "experiment_id": f"e2-10-valence-operational-gate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_sensitivity_csv": str(args.sensitivity_csv),
        "decision": {
            "mode": mode,
            "global_user_facing_allowed": False,
            "scoped_internal_allowed": mode == "internal_scoped",
        },
    }
    (out / "evaluation-report.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "research-report.md").write_text(
        "\n".join(
            [
                "# E2.10 Scoped Valence Operational Gate",
                "",
                f"- Mode: `{mode}`",
                f"- Scoped internal allowed: `{mode == 'internal_scoped'}`",
                "- User-facing claims: `false`",
                "- Auto-personalization trigger: `false`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return gate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.10 valence scoped operational gate")
    parser.add_argument(
        "--sensitivity-csv",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-9-valence-policy-sensitivity/sensitivity-summary.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
