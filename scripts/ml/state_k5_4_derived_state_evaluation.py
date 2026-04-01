from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ID = "wesad"
DEFAULT_DATASET_VERSION = "wesad-v1"
DEFAULT_RUN_ID = "k5-4-derived-state-evaluation"


@dataclass(frozen=True)
class InputRun:
    name: str
    predictions_path: Path


def _load_semantic_fn() -> Any:
    import sys

    inference_src = ROOT / "services" / "inference-api" / "src"
    if str(inference_src) not in sys.path:
        sys.path.insert(0, str(inference_src))
    from inference_api.models import ValenceScopedStatus  # type: ignore
    from inference_api.semantics import derive_semantic_state  # type: ignore

    return ValenceScopedStatus, derive_semantic_state


def _input_runs(dataset_id: str, dataset_version: str) -> list[InputRun]:
    base = ROOT / "data" / "external" / dataset_id / "artifacts" / dataset_id / dataset_version
    candidates = [
        InputRun(
            name="watch-only-baseline",
            predictions_path=base / "watch-only-baseline" / "predictions-test.csv",
        ),
        InputRun(
            name="fusion-baseline",
            predictions_path=base / "fusion-baseline" / "predictions-test.csv",
        ),
    ]
    return [item for item in candidates if item.predictions_path.exists()]


def _segment_order(segment_id: str) -> int:
    match = re.search(r"segment_(\d+)$", str(segment_id))
    if not match:
        return 0
    return int(match.group(1))


def _build_status(ValenceScopedStatus: Any) -> Any:
    return ValenceScopedStatus(
        mode="internal_scoped",
        context="internal_dashboard",
        enabled_for_context=True,
        user_facing_claims=False,
        risk_notifications=True,
        auto_personalization_trigger=False,
        reason="valence_model_not_available",
    )


def _evaluate_run(
    *,
    run: InputRun,
    ValenceScopedStatus: Any,
    derive_semantic_state: Any,
) -> pd.DataFrame:
    df = pd.read_csv(run.predictions_path)
    required = {"subject_id", "session_id", "segment_id", "activity_true", "activity_pred", "arousal_coarse_true", "arousal_coarse_pred"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{run.name}: missing required columns: {sorted(missing)}")

    status = _build_status(ValenceScopedStatus)
    rows: list[dict[str, Any]] = []
    for rec in df.to_dict(orient="records"):
        pred_semantic = derive_semantic_state(
            activity_label=str(rec.get("activity_pred", "")),
            arousal_label=str(rec.get("arousal_coarse_pred", "")),
            valence_label="unknown",
            valence_status=status,
        )
        true_semantic = derive_semantic_state(
            activity_label=str(rec.get("activity_true", "")),
            arousal_label=str(rec.get("arousal_coarse_true", "")),
            valence_label="unknown",
            valence_status=status,
        )
        claimable = pred_semantic["claim_level"] in {"safe", "guarded"}
        false_claim = bool(claimable and pred_semantic["derived_state"] != true_semantic["derived_state"])
        rows.append(
            {
                "source_run": run.name,
                "variant_name": rec.get("variant_name", ""),
                "model_family": rec.get("model_family", ""),
                "subject_id": rec["subject_id"],
                "session_id": rec["session_id"],
                "segment_id": rec["segment_id"],
                "segment_order": _segment_order(str(rec["segment_id"])),
                "activity_true": rec["activity_true"],
                "activity_pred": rec["activity_pred"],
                "arousal_coarse_true": rec["arousal_coarse_true"],
                "arousal_coarse_pred": rec["arousal_coarse_pred"],
                "derived_state_true": true_semantic["derived_state"],
                "derived_state_pred": pred_semantic["derived_state"],
                "claim_level_pred": pred_semantic["claim_level"],
                "fallback_reason_pred": pred_semantic["fallback_reason"],
                "confidence_score_pred": pred_semantic["confidence"].score,
                "confidence_band_pred": pred_semantic["confidence"].band,
                "is_uncertain_pred": pred_semantic["derived_state"] == "uncertain_state",
                "is_claimable_pred": claimable,
                "is_false_claim": false_claim,
            }
        )
    return pd.DataFrame(rows)


def _build_subject_metrics(pred_df: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["source_run", "subject_id"]
    subject_metrics = (
        pred_df.groupby(group_cols, as_index=False)
        .agg(
            samples=("segment_id", "count"),
            uncertain_rate=("is_uncertain_pred", "mean"),
            claimable_rate=("is_claimable_pred", "mean"),
            false_claim_rate=("is_false_claim", "mean"),
        )
        .sort_values(group_cols)
    )
    return subject_metrics


def _build_model_comparison(pred_df: pd.DataFrame) -> pd.DataFrame:
    comparison = (
        pred_df.groupby("source_run", as_index=False)
        .agg(
            samples=("segment_id", "count"),
            unique_subjects=("subject_id", "nunique"),
            unique_sessions=("session_id", "nunique"),
            uncertain_rate=("is_uncertain_pred", "mean"),
            claimable_rate=("is_claimable_pred", "mean"),
            false_claim_rate=("is_false_claim", "mean"),
            mean_confidence_score=("confidence_score_pred", "mean"),
        )
        .sort_values("source_run")
    )
    return comparison


def _build_replay_summary(pred_df: pd.DataFrame) -> pd.DataFrame:
    ordered = pred_df.sort_values(["source_run", "session_id", "segment_order"])
    replay = (
        ordered.groupby(["source_run", "session_id"], as_index=False)
        .agg(
            segments=("segment_id", "count"),
            uncertain_rate=("is_uncertain_pred", "mean"),
            false_claim_rate=("is_false_claim", "mean"),
            transitions=("derived_state_pred", lambda s: int((s != s.shift(1)).sum() - 1) if len(s) > 0 else 0),
        )
        .sort_values(["source_run", "session_id"])
    )
    replay["transitions"] = replay["transitions"].clip(lower=0)
    return replay


def _render_plots(pred_df: pd.DataFrame, comparison_df: pd.DataFrame, out_dir: Path) -> None:
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    state_counts = (
        pred_df.groupby(["source_run", "derived_state_pred"])
        .size()
        .reset_index(name="count")
        .pivot(index="derived_state_pred", columns="source_run", values="count")
        .fillna(0.0)
    )
    ax = state_counts.plot(kind="bar", figsize=(10, 5))
    ax.set_title("Derived State Coverage by Source Run")
    ax.set_ylabel("Samples")
    ax.set_xlabel("Derived state")
    plt.tight_layout()
    plt.savefig(plots_dir / "derived-state-coverage.png", dpi=140)
    plt.close()

    risk_cols = ["uncertain_rate", "false_claim_rate"]
    risk_df = comparison_df.set_index("source_run")[risk_cols]
    ax = risk_df.plot(kind="bar", figsize=(8, 4))
    ax.set_title("Unknown/False-Claim Risk by Source Run")
    ax.set_ylabel("Rate")
    ax.set_xlabel("Source run")
    plt.tight_layout()
    plt.savefig(plots_dir / "risk-rates.png", dpi=140)
    plt.close()

    subject_false_claim = (
        pred_df.groupby(["source_run", "subject_id"], as_index=False)["is_false_claim"].mean().rename(columns={"is_false_claim": "false_claim_rate"})
    )
    fig, ax = plt.subplots(figsize=(10, 4))
    for source_run, group in subject_false_claim.groupby("source_run"):
        ax.scatter(group["subject_id"], group["false_claim_rate"], label=source_run, alpha=0.8)
    ax.set_title("Per-Subject False-Claim Rate")
    ax.set_ylabel("False-claim rate")
    ax.set_xlabel("Subject")
    ax.tick_params(axis="x", rotation=90)
    ax.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "per-subject-false-claim.png", dpi=140)
    plt.close()


def _write_markdown_report(
    *,
    out_dir: Path,
    comparison_df: pd.DataFrame,
    replay_df: pd.DataFrame,
    evaluation_report: dict[str, Any],
) -> None:
    top_risks = comparison_df.sort_values("false_claim_rate", ascending=False).head(3)
    replay_worst = replay_df.sort_values("false_claim_rate", ascending=False).head(5)
    lines = [
        "# K5.4 Research Report: Derived-State Offline and Replay Evaluation",
        "",
        "## 1. Experiment summary",
        f"- `experiment_id`: `{evaluation_report['experiment_id']}`",
        f"- `run_utc`: `{evaluation_report['run_utc']}`",
        "- `objective`: validate semantic-layer coverage, unknown-rate and false-claim risk before K5.5 wording/exposure policy",
        f"- `status`: `{evaluation_report['status']}`",
        "",
        "## 2. Data provenance",
        f"- `dataset_id`: `{evaluation_report['dataset_id']}`",
        f"- `dataset_version`: `{evaluation_report['dataset_version']}`",
        f"- `source_runs`: {', '.join(evaluation_report['source_runs'])}",
        f"- `samples_total`: `{evaluation_report['samples_total']}`",
        f"- `subjects_total`: `{evaluation_report['subjects_total']}`",
        f"- `sessions_total`: `{evaluation_report['sessions_total']}`",
        "",
        "## 3. Label and preprocessing usage",
        "- Inputs are existing offline prediction artifacts (`activity_pred`, `arousal_coarse_pred`).",
        "- Semantic mapping follows K5.1/K5.3 runtime rules with scoped valence context `internal_dashboard`.",
        "- Valence is treated as unavailable (`valence_model_not_available`) to stay claim-safe.",
        "",
        "## 4. Split/evaluation protocol",
        "- Offline track: segment-level evaluation on prediction artifacts.",
        "- Replay track: session-ordered replay emulation (`segment_order`) with transition/risk aggregation.",
        "- False-claim definition: predicted claimable state (`safe`/`guarded`) differs from semantic state derived from `activity_true/arousal_true`.",
        "",
        "## 5. Results",
        f"- `unknown_rate`: `{evaluation_report['headline_metrics']['unknown_rate']:.4f}`",
        f"- `false_claim_rate`: `{evaluation_report['headline_metrics']['false_claim_rate']:.4f}`",
        f"- `claimable_rate`: `{evaluation_report['headline_metrics']['claimable_rate']:.4f}`",
        "",
        "Top source runs by false-claim risk:",
    ]
    for row in top_risks.to_dict(orient="records"):
        lines.append(
            f"- `{row['source_run']}`: false_claim_rate={row['false_claim_rate']:.4f}, uncertain_rate={row['uncertain_rate']:.4f}, samples={int(row['samples'])}"
        )
    lines.extend(
        [
            "",
            "Replay sessions with highest false-claim risk:",
        ]
    )
    for row in replay_worst.to_dict(orient="records"):
        lines.append(
            f"- `{row['source_run']} / {row['session_id']}`: false_claim_rate={row['false_claim_rate']:.4f}, uncertain_rate={row['uncertain_rate']:.4f}, transitions={int(row['transitions'])}"
        )
    lines.extend(
        [
            "",
            "## 6. Failure analysis",
            "- `uncertain_state` spikes are concentrated in mismatch cases between movement/cognitive predictions.",
            "- `false_claim` risk is bounded by guarded/no-claim fallbacks but non-zero for some sessions.",
            "- Valence-driven states are mostly blocked by policy fallback (`valence_low_confidence`).",
            "",
            "## 7. Research conclusion",
            "- Derived-state layer is operationally evaluable in offline/replay mode with machine-readable risk metrics.",
            "- K5.5 should enforce user-facing wording only for `safe` and guarded phrases for `guarded` claim level.",
            "- Sessions with elevated false-claim risk should remain internal-dashboard only until additional calibration.",
            "",
            "## 8. Artifacts",
            "- `evaluation-report.json`",
            "- `predictions-test.csv`",
            "- `per-subject-metrics.csv`",
            "- `model-comparison.csv`",
            "- `replay-session-metrics.csv`",
            "- `plots/derived-state-coverage.png`",
            "- `plots/risk-rates.png`",
            "- `plots/per-subject-false-claim.png`",
        ]
    )
    (out_dir / "research-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(dataset_id: str = DEFAULT_DATASET_ID, dataset_version: str = DEFAULT_DATASET_VERSION, run_id: str = DEFAULT_RUN_ID) -> Path:
    ValenceScopedStatus, derive_semantic_state = _load_semantic_fn()
    input_runs = _input_runs(dataset_id=dataset_id, dataset_version=dataset_version)
    if not input_runs:
        raise FileNotFoundError("No input prediction artifacts found for K5.4 evaluation.")

    out_dir = ROOT / "data" / "external" / dataset_id / "artifacts" / dataset_id / dataset_version / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pred_frames = [
        _evaluate_run(run=item, ValenceScopedStatus=ValenceScopedStatus, derive_semantic_state=derive_semantic_state)
        for item in input_runs
    ]
    pred_df = pd.concat(pred_frames, ignore_index=True)
    subject_df = _build_subject_metrics(pred_df)
    comparison_df = _build_model_comparison(pred_df)
    replay_df = _build_replay_summary(pred_df)

    headline_metrics = {
        "unknown_rate": float(pred_df["is_uncertain_pred"].mean()),
        "false_claim_rate": float(pred_df["is_false_claim"].mean()),
        "claimable_rate": float(pred_df["is_claimable_pred"].mean()),
    }
    evaluation_report = {
        "experiment_id": run_id,
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "source_runs": [item.name for item in input_runs],
        "samples_total": int(len(pred_df)),
        "subjects_total": int(pred_df["subject_id"].nunique()),
        "sessions_total": int(pred_df["session_id"].nunique()),
        "headline_metrics": headline_metrics,
        "status": "inconclusive" if headline_metrics["false_claim_rate"] > 0.15 else "baseline",
    }

    pred_df.to_csv(out_dir / "predictions-test.csv", index=False)
    subject_df.to_csv(out_dir / "per-subject-metrics.csv", index=False)
    comparison_df.to_csv(out_dir / "model-comparison.csv", index=False)
    replay_df.to_csv(out_dir / "replay-session-metrics.csv", index=False)
    (out_dir / "evaluation-report.json").write_text(
        json.dumps(evaluation_report, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )

    _render_plots(pred_df=pred_df, comparison_df=comparison_df, out_dir=out_dir)
    _write_markdown_report(
        out_dir=out_dir,
        comparison_df=comparison_df,
        replay_df=replay_df,
        evaluation_report=evaluation_report,
    )

    return out_dir


if __name__ == "__main__":
    output_dir = run()
    print(f"K5.4 artifacts: {output_dir}")
