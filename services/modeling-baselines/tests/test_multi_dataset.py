from modeling_baselines.multi_dataset import (
    Example,
    _apply_pseudo_label_guardrails,
    _build_execution_comparison_rows,
    _build_phase_execution_rows,
    _build_pseudo_label_candidate_pool,
    _build_self_training_metrics_contract,
    _build_self_training_phase_rows,
    _pseudo_rows_for_csv,
    _build_protocol_readiness_rows,
    _build_training_phases,
    _classify_arousal_label_quality,
    _drop_models,
    _recommended_arousal_role,
    _select_safe_feature_names,
)


def test_select_safe_feature_names_rejects_label_and_meta_shortcuts() -> None:
    selected = _select_safe_feature_names(
        [
            "meta_segment_duration_sec",
            "meta_source_sample_count",
            "label_source_value_numeric",
            "label_source_label_hash",
            "watch_acc_c0__mean",
            "signal_hr_mean",
        ]
    )
    assert selected == ["watch_acc_c0__mean", "signal_hr_mean"]


def test_classify_arousal_label_quality_distinguishes_real_protocol_and_proxy() -> None:
    assert _classify_arousal_label_quality(
        {
            "dataset_id": "grex",
            "target_tracks": ["activity/context", "arousal"],
            "labels_available": ["arousal_1to5", "activity_label"],
        }
    ) == "real_annotation_mapped"
    assert _classify_arousal_label_quality(
        {
            "dataset_id": "wesad",
            "target_tracks": ["activity/context", "arousal"],
            "labels_available": ["wesad_state", "arousal_score"],
        }
    ) == "protocol_state_mapped"
    assert _classify_arousal_label_quality(
        {
            "dataset_id": "emowear",
            "target_tracks": ["activity/context", "arousal_proxy"],
            "labels_available": ["arousal_score_proxy"],
        }
    ) == "proxy_label"


def test_recommended_arousal_role_respects_coverage_guardrail() -> None:
    assert _recommended_arousal_role("real_annotation_mapped", "ready") == "primary_supervision"
    assert _recommended_arousal_role("protocol_state_mapped", "ready") == "protocol_transfer_or_eval"
    assert _recommended_arousal_role("proxy_label", "ready") == "auxiliary_pretraining"
    assert _recommended_arousal_role("real_annotation_mapped", "missing_artifacts") == "skip"


def test_build_training_phases_orders_proxy_real_and_protocol_roles() -> None:
    phases = _build_training_phases(
        [
            {"dataset_id": "emowear", "dataset_version": "emowear-v1", "recommended_role": "auxiliary_pretraining", "coverage_status": "ready"},
            {"dataset_id": "grex", "dataset_version": "grex-v1", "recommended_role": "primary_supervision", "coverage_status": "ready"},
            {"dataset_id": "wesad", "dataset_version": "wesad-v1", "recommended_role": "protocol_transfer_or_eval", "coverage_status": "ready"},
            {"dataset_id": "dapper", "dataset_version": "dapper-v1", "recommended_role": "skip", "coverage_status": "insufficient_train_test"},
        ]
    )
    assert [item["phase_name"] for item in phases] == [
        "proxy_pretraining",
        "real_label_finetune",
        "protocol_transfer",
        "cross_dataset_evaluation",
    ]
    assert phases[0]["datasets"] == "emowear:emowear-v1"
    assert phases[1]["datasets"] == "grex:grex-v1"
    assert phases[2]["datasets"] == "wesad:wesad-v1"
    assert phases[3]["datasets"] == "emowear:emowear-v1,grex:grex-v1,wesad:wesad-v1"


def test_protocol_readiness_and_phase_execution_block_without_harmonized_features() -> None:
    dataset_rows = [
        {
            "dataset_id": "emowear",
            "dataset_version": "emowear-v1",
            "recommended_role": "auxiliary_pretraining",
            "coverage_status": "ready",
        },
        {
            "dataset_id": "grex",
            "dataset_version": "grex-v1",
            "recommended_role": "primary_supervision",
            "coverage_status": "ready",
        },
        {
            "dataset_id": "wesad",
            "dataset_version": "wesad-v1",
            "recommended_role": "protocol_transfer_or_eval",
            "coverage_status": "ready",
        },
        {
            "dataset_id": "dapper",
            "dataset_version": "dapper-v1",
            "recommended_role": "skip",
            "coverage_status": "insufficient_train_test",
        },
    ]
    phases = _build_training_phases(dataset_rows)
    readiness = _build_protocol_readiness_rows(dataset_rows)
    phase_rows = _build_phase_execution_rows(phases, readiness)

    failed_checks = [row for row in readiness if row["status"] == "failed"]
    skipped_checks = [row for row in readiness if row["status"] == "skipped"]
    assert failed_checks
    assert skipped_checks
    assert any(row["check"] == "harmonized_signal_features" for row in failed_checks)
    assert any(row["check"] == "dataset_coverage" for row in skipped_checks)
    assert all(row["status"] == "blocked" for row in phase_rows)


def test_self_training_phase_rows_ready_when_protocol_ready() -> None:
    protocol_phase_rows = [
        {"phase_name": "proxy_pretraining", "status": "ready"},
        {"phase_name": "real_label_finetune", "status": "ready"},
        {"phase_name": "protocol_transfer", "status": "ready"},
        {"phase_name": "cross_dataset_evaluation", "status": "ready"},
    ]
    readiness_rows = [
        {"dataset": "emowear:emowear-v1", "check": "dataset_coverage", "status": "passed"},
        {"dataset": "grex:grex-v1", "check": "dataset_coverage", "status": "passed"},
    ]

    rows = _build_self_training_phase_rows(protocol_phase_rows=protocol_phase_rows, readiness_rows=readiness_rows)
    assert len(rows) == 9
    assert all(row["status"] == "ready" for row in rows)
    assert rows[0]["phase_name"] == "freeze_gates"
    assert rows[-1]["phase_name"] == "model_freeze_decision"


def test_self_training_phase_rows_block_when_protocol_blocked() -> None:
    protocol_phase_rows = [
        {"phase_name": "proxy_pretraining", "status": "ready"},
        {"phase_name": "real_label_finetune", "status": "blocked"},
        {"phase_name": "protocol_transfer", "status": "ready"},
        {"phase_name": "cross_dataset_evaluation", "status": "ready"},
    ]
    readiness_rows = [{"dataset": "grex:grex-v1", "check": "dataset_coverage", "status": "failed"}]

    rows = _build_self_training_phase_rows(protocol_phase_rows=protocol_phase_rows, readiness_rows=readiness_rows)
    blocked = [row for row in rows if row["status"] == "blocked"]
    assert blocked
    assert blocked[0]["phase_name"] == "freeze_gates"
    assert all("upstream:blocking_phase" in row["blockers"] or row["phase_name"] == "freeze_gates" for row in blocked)


def test_self_training_metrics_contract_includes_final_gate() -> None:
    rows = _build_self_training_metrics_contract()
    assert any(
        row["phase_name"] == "model_freeze_decision"
        and row["metric_name"] == "promotion_decision"
        for row in rows
    )


def test_drop_models_removes_runtime_model_objects() -> None:
    payload = {
        "phase_7": {
            "supervised_model": object(),
            "self_trained_model": object(),
            "rows": [{"dataset": "grex:grex-v1"}],
        }
    }
    clean = _drop_models(payload)
    assert "supervised_model" not in clean["phase_7"]
    assert "self_trained_model" not in clean["phase_7"]


def test_build_execution_comparison_rows_merges_phase_outputs() -> None:
    rows = _build_execution_comparison_rows(
        phase1={"phase_name": "proxy_pretraining", "rows": [{"dataset": "emowear:emowear-v1", "kind": "gaussian_nb", "track": "arousal_coarse", "macro_f1": 0.5, "balanced_accuracy": 0.5}]},
        phase2={"phase_name": "real_label_finetune", "rows": [{"dataset": "grex:grex-v1", "kind": "catboost", "track": "arousal_coarse", "macro_f1": 0.6, "balanced_accuracy": 0.6}]},
        phase3={"phase_name": "protocol_transfer", "status": "ready", "dataset": "wesad:wesad-v1", "model_kind": "catboost", "track": "arousal_coarse", "macro_f1": 0.4, "balanced_accuracy": 0.4},
        phase7={"rows": [{"dataset": "grex:grex-v1", "model_variant": "catboost_self_trained", "track": "arousal_coarse", "macro_f1": 0.61, "balanced_accuracy": 0.61}]},
    )
    assert len(rows) == 4
    assert any(row["phase_name"] == "cross_dataset_evaluation" for row in rows)


def test_build_pseudo_label_candidate_pool_excludes_primary_dataset() -> None:
    primary = "grex:grex-v1"
    item = Example(
        dataset_id="emowear",
        dataset_version="emowear-v1",
        subject_id="emowear:01",
        session_id="emowear:emowear-v1:01:c1",
        segment_id="emowear:emowear-v1:01:seg_1",
        split="train",
        activity_label="focused_cognitive_task",
        arousal_coarse="high",
        features={"signal_x__mean": 1.0},
    )
    pool = _build_pseudo_label_candidate_pool(
        examples_by_dataset={
            "grex:grex-v1": {"train": [item], "validation": []},
            "emowear:emowear-v1": {"train": [item], "validation": [item]},
        },
        primary_dataset_key=primary,
    )
    assert len(pool) == 2


def test_pseudo_rows_for_csv_drops_feature_values() -> None:
    rows = _pseudo_rows_for_csv(
        [
            {
                "dataset_id": "emowear",
                "dataset_version": "emowear-v1",
                "subject_id": "emowear:01",
                "session_id": "emowear:emowear-v1:01:c1",
                "segment_id": "emowear:emowear-v1:01:seg_1",
                "pseudo_arousal_coarse": "high",
                "agreement_rule": "teacher_equals_shadow",
                "feature_values": [0.1, 0.2],
            }
        ]
    )
    assert len(rows) == 1
    assert "feature_values" not in rows[0]


def test_apply_pseudo_label_guardrails_caps_acceptance_and_single_class() -> None:
    rows = [
        {
            "dataset_id": "emowear",
            "dataset_version": "emowear-v1",
            "subject_id": f"emowear:{idx:02d}",
            "session_id": f"session_{idx:03d}",
            "segment_id": f"seg_{idx:03d}",
            "pseudo_arousal_coarse": "medium",
            "agreement_rule": "committee_vote_2_of_3",
            "vote_count": 2,
            "feature_values": [0.1, 0.2],
        }
        for idx in range(100)
    ]
    filtered, report = _apply_pseudo_label_guardrails(
        rows=rows,
        candidate_count=100,
        max_acceptance_rate=0.6,
        max_class_share=0.75,
        single_class_max_keep=25,
    )
    assert report["applied"] is True
    assert report["before_count"] == 100
    assert report["after_count"] == 25
    assert len(filtered) == 25
