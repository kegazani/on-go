from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from modeling_baselines.pipeline import _claim_status_from_delta


M73_ABLATION_VARIANTS = ("polar_only", "watch_motion_only", "polar+watch_motion")
M73_TRACKS = ("activity", "arousal_coarse", "valence_coarse")
M73_RESEARCH_REPORT_SECTIONS = (
    "Experiment summary",
    "Data provenance",
    "Label definition and usage",
    "Preprocessing and features",
    "Split and evaluation protocol",
    "Model definition",
    "Results",
    "Failure analysis",
    "Research conclusion",
    "Interpretation limits",
)


def _build_m73_ablation_rows(track_scores: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    baseline_scores = track_scores["polar_only"]
    rows: list[dict[str, Any]] = []
    for variant_name in M73_ABLATION_VARIANTS:
        for track_name in M73_TRACKS:
            value = track_scores[variant_name][track_name]
            delta = round(value - baseline_scores[track_name], 6)
            claim_status = "baseline" if variant_name == "polar_only" else _claim_status_from_delta(
                delta_value=delta,
                delta_ci=[delta - 0.05, delta + 0.05],
            )
            rows.append(
                {
                    "variant_name": variant_name,
                    "track": track_name,
                    "baseline_name": "polar_only",
                    "metric_name": "macro_f1",
                    "value": value,
                    "delta_vs_polar_only": delta,
                    "claim_status": claim_status,
                }
            )
    return rows


def _anti_collapse_signal(predictions: list[str], *, stress_set_name: str) -> dict[str, Any]:
    counts = Counter(predictions)
    dominant_class, dominant_count = counts.most_common(1)[0]
    return {
        "stress_set_name": stress_set_name,
        "predicted_class_count": len(counts),
        "dominant_class": dominant_class,
        "dominant_class_share": round(dominant_count / len(predictions), 6),
        "is_collapsed": len(counts) == 1,
    }


def test_m73_ablation_matrix_contract_uses_polar_first_baseline() -> None:
    rows = _build_m73_ablation_rows(
        {
            "polar_only": {
                "activity": 0.42,
                "arousal_coarse": 0.37,
                "valence_coarse": 0.31,
            },
            "watch_motion_only": {
                "activity": 0.52,
                "arousal_coarse": 0.45,
                "valence_coarse": 0.39,
            },
            "polar+watch_motion": {
                "activity": 0.60,
                "arousal_coarse": 0.54,
                "valence_coarse": 0.48,
            },
        }
    )

    assert [row["variant_name"] for row in rows[:3]] == ["polar_only", "polar_only", "polar_only"]
    assert {row["variant_name"] for row in rows} == set(M73_ABLATION_VARIANTS)
    assert len(rows) == len(M73_ABLATION_VARIANTS) * len(M73_TRACKS)
    assert all(row["baseline_name"] == "polar_only" for row in rows)
    assert all(row["claim_status"] == "baseline" for row in rows[:3])
    assert all(
        row["claim_status"] == "supported"
        for row in rows
        if row["variant_name"] == "watch_motion_only" or row["variant_name"] == "polar+watch_motion"
    )


def test_m73_anti_collapse_signal_flags_single_class_predictions() -> None:
    signal = _anti_collapse_signal(["low"] * 16, stress_set_name="validation_stress")
    assert signal == {
        "stress_set_name": "validation_stress",
        "predicted_class_count": 1,
        "dominant_class": "low",
        "dominant_class_share": 1.0,
        "is_collapsed": True,
    }


def test_m73_anti_collapse_signal_keeps_multi_class_predictions_open() -> None:
    signal = _anti_collapse_signal(
        ["low", "medium", "low", "high", "medium", "low"],
        stress_set_name="validation_stress",
    )
    assert signal["predicted_class_count"] == 3
    assert signal["dominant_class"] == "low"
    assert signal["dominant_class_share"] == 0.5
    assert signal["is_collapsed"] is False


def test_m73_reporting_template_matches_model_reporting_standard_sections() -> None:
    root = Path(__file__).resolve().parents[3]
    readme_text = (root / "services/modeling-baselines/README.md").read_text(encoding="utf-8")
    doc_text = (root / "docs/backend/m7-3-polar-first-ablation-contract.md").read_text(encoding="utf-8")

    for needle in (
        "polar_only",
        "watch_motion_only",
        "polar+watch_motion",
        "anti-collapse",
        "evaluation-report.json",
        "research-report.md",
    ):
        assert needle in readme_text
        assert needle in doc_text

    for section in M73_RESEARCH_REPORT_SECTIONS:
        assert section in doc_text


def test_m741_remediation_loop_doc_spells_out_completion_criteria() -> None:
    root = Path(__file__).resolve().parents[3]
    readme_text = (root / "services/modeling-baselines/README.md").read_text(encoding="utf-8")
    doc_text = (root / "docs/backend/m7-4-1-remediation-loop.md").read_text(encoding="utf-8")

    for needle in (
        "M7.4.1",
        "gate_passed",
        "track_failures",
        "global_issues",
        "remediation_actions",
        "P4 remediation loop",
        "P5 Runtime Bundle Export",
    ):
        assert needle in readme_text
        assert needle in doc_text

    for needle in (
        "Completion Criteria",
        "source `M7.3` report",
        "anti_collapse_summary.passed",
        "flagged_rows",
        "claim_status",
        "anti_collapse_status",
    ):
        assert needle in doc_text
