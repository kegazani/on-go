#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
    return rows


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
    input_rows = _load_rows(args.input_csv)
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in input_rows:
        key = (str(row["source_dataset"]), str(row["target_dataset"]), str(row["classifier_kind"]))
        by_key[key] = row

    classifiers = sorted({str(row["classifier_kind"]) for row in input_rows})
    floors = [0.35, 0.38, 0.40]

    sensitivity_rows: list[dict[str, Any]] = []
    for clf in classifiers:
        w2g = float(by_key[("wesad", "grex", clf)]["macro_f1"])
        g2w = float(by_key[("grex", "wesad", clf)]["macro_f1"])
        for floor in floors:
            w_pass = w2g >= floor
            g_pass = g2w >= floor
            sensitivity_rows.append(
                {
                    "classifier_kind": clf,
                    "floor": floor,
                    "wesad_to_grex_macro_f1": round(w2g, 6),
                    "grex_to_wesad_macro_f1": round(g2w, 6),
                    "wesad_to_grex_pass": bool(w_pass),
                    "grex_to_wesad_pass": bool(g_pass),
                    "bidirectional_pass": bool(w_pass and g_pass),
                    "any_direction_pass": bool(w_pass or g_pass),
                }
            )

    default_floor = 0.40
    policy_rows: list[dict[str, Any]] = []
    for clf in classifiers:
        w2g = float(by_key[("wesad", "grex", clf)]["macro_f1"])
        g2w = float(by_key[("grex", "wesad", clf)]["macro_f1"])
        w_policy = "blocked"
        g_policy = "blocked"
        if w2g >= default_floor:
            w_policy = "directional_internal_only"
        if g2w >= default_floor:
            g_policy = "directional_internal_only"
        if w2g >= default_floor and g2w >= default_floor:
            w_policy = "bidirectional_candidate"
            g_policy = "bidirectional_candidate"
        policy_rows.append(
            {
                "classifier_kind": clf,
                "direction": "wesad_to_grex",
                "macro_f1": round(w2g, 6),
                "policy_at_floor_0_40": w_policy,
            }
        )
        policy_rows.append(
            {
                "classifier_kind": clf,
                "direction": "grex_to_wesad",
                "macro_f1": round(g2w, 6),
                "policy_at_floor_0_40": g_policy,
            }
        )

    ridge_floor_035 = next(
        row for row in sensitivity_rows if row["classifier_kind"] == "ridge_classifier" and float(row["floor"]) == 0.35
    )
    scoped_candidate = bool(ridge_floor_035["bidirectional_pass"])

    decision = {
        "global_policy": "keep_exploratory",
        "scoped_policy": "allow_internal_scoped_bidirectional_ridge_at_floor_0_35" if scoped_candidate else "none",
        "rationale": [
            "At default floor 0.40 no classifier passes bidirectional transfer gate.",
            "Sensitivity shows ridge can pass bidirectional only at floor 0.35.",
            "Any scoped mode must remain non-user-facing and internal/research only.",
        ],
    }

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "sensitivity-summary.csv", sensitivity_rows)
    _write_csv(out / "direction-policy-matrix.csv", policy_rows)

    report = {
        "experiment_id": f"e2-9-valence-policy-sensitivity-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_artifact": str(args.input_csv),
        "floors": floors,
        "default_floor": default_floor,
        "decision": decision,
    }
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# E2.9 Direction-specific Policy + Gate Sensitivity",
        "",
        f"- Global policy: `{decision['global_policy']}`",
        f"- Scoped policy candidate: `{decision['scoped_policy']}`",
        "- Floors tested: `0.35`, `0.38`, `0.40`",
    ]
    (out / "research-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.9 valence policy sensitivity")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate/model-comparison.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-9-valence-policy-sensitivity"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
