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


def _evaluate(policy: dict[str, Any], mode: str, context: str) -> dict[str, Any]:
    guardrails = policy.get("guardrails", {}) if isinstance(policy.get("guardrails"), dict) else {}
    allowed = [str(item) for item in policy.get("allowed_contexts", [])]
    enabled = mode != "disabled" and context in allowed
    return {
        "mode": mode,
        "context": context,
        "enabled_for_context": bool(enabled),
        "user_facing_claims": bool(guardrails.get("user_facing_claims", False)),
        "risk_notifications": bool(guardrails.get("risk_notifications", False)),
        "auto_personalization_trigger": bool(guardrails.get("auto_personalization_trigger", False)),
        "reason": "context_not_allowed" if mode != "disabled" and context not in allowed else ("policy_disabled" if mode == "disabled" else "valence_model_not_available"),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    base = json.loads(args.scoped_policy.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for mode in ("disabled", "internal_scoped"):
        policy = dict(base)
        policy["mode"] = mode
        for context in ("research_only", "internal_dashboard", "shadow_mode", "public_app"):
            rows.append(_evaluate(policy, mode=mode, context=context))

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "dryrun-mode-matrix.csv", rows)
    report = {
        "experiment_id": f"e2-11-runtime-dryrun-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scoped_policy_path": str(args.scoped_policy),
        "modes_tested": ["disabled", "internal_scoped"],
        "contexts_tested": ["research_only", "internal_dashboard", "shadow_mode", "public_app"],
    }
    (out / "dryrun-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "dryrun-report.md").write_text(
        "\n".join(
            [
                "# E2.11 Runtime Dry-run",
                "",
                "- Modes: `disabled`, `internal_scoped`",
                "- Contexts: `research_only`, `internal_dashboard`, `shadow_mode`, `public_app`",
                "- Expected: `public_app` always blocked; `disabled` blocks all contexts.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.11 scoped mode runtime dry-run")
    parser.add_argument(
        "--scoped-policy",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/scoped-policy.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-11-runtime-dryrun"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
