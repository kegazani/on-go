from __future__ import annotations

from modeling_baselines.audit import (
    _blocking_findings,
    _coverage_counts,
    _has_blocking_findings,
    _is_forbidden_feature_name,
    _subject_overlap_pairs,
)
from modeling_baselines.pipeline import SegmentExample


def _example(
    subject_id: str,
    session_id: str,
    segment_id: str,
    split: str,
    activity_label: str,
    arousal_coarse: str,
) -> SegmentExample:
    return SegmentExample(
        dataset_id="wesad",
        dataset_version="wesad-v1",
        subject_id=subject_id,
        session_id=session_id,
        segment_id=segment_id,
        split=split,
        activity_label=activity_label,
        arousal_score=2 if arousal_coarse == "low" else 8,
        arousal_coarse=arousal_coarse,
        valence_score=5,
        valence_coarse="neutral",
        source_label_value="1",
        features={"watch_acc_c0__mean": 0.1},
    )


def test_is_forbidden_feature_name_catches_shortcuts() -> None:
    assert _is_forbidden_feature_name("meta_segment_duration_sec")
    assert _is_forbidden_feature_name("label_source_value_numeric")
    assert not _is_forbidden_feature_name("watch_acc_c0__mean")


def test_subject_overlap_pairs_reports_train_test_overlap() -> None:
    manifest = {
        "train_subject_ids": ["wesad:S2", "wesad:S3"],
        "validation_subject_ids": ["wesad:S4"],
        "test_subject_ids": ["wesad:S3", "wesad:S5"],
    }
    overlaps = _subject_overlap_pairs(manifest)
    assert overlaps == [
        {
            "left": "train_subject_ids",
            "right": "test_subject_ids",
            "overlap_subject_ids": ["wesad:S3"],
        }
    ]


def test_coverage_counts_returns_sorted_counts() -> None:
    rows = [
        _example("wesad:S2", "s2", "seg1", "train", "seated_rest", "low"),
        _example("wesad:S3", "s3", "seg2", "train", "focused_cognitive_task", "high"),
        _example("wesad:S4", "s4", "seg3", "train", "seated_rest", "low"),
    ]
    assert _coverage_counts(rows, "activity_label") == {
        "focused_cognitive_task": 1,
        "seated_rest": 2,
    }


def test_blocking_findings_are_reported_when_alerts_exist() -> None:
    split_audit = {
        "subject_overlap_pairs": [{"left": "train_subject_ids", "right": "test_subject_ids", "overlap_subject_ids": ["wesad:S9"]}],
        "duplicate_segment_ids": 1,
    }
    leakage_audit = {
        "forbidden_selected_features": ["label_source_value_numeric"],
        "alerts": {
            "activity_single_feature_shortcut": True,
            "arousal_single_feature_shortcut": False,
            "valence_single_feature_shortcut": False,
        },
    }
    assert _has_blocking_findings(split_audit, leakage_audit)
    assert _blocking_findings(split_audit, leakage_audit) == [
        "split_subject_overlap",
        "duplicate_segment_ids",
        "forbidden_selected_features",
        "activity_single_feature_shortcut",
    ]
