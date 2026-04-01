from __future__ import annotations

from live_inference_api.semantics import build_valence_scoped_status, derive_semantic_state


def test_live_status_public_app_allows_valence_when_model_present() -> None:
    status = build_valence_scoped_status(context="public_app", has_valence_model=True)
    assert status["enabled_for_context"] is True
    assert status["reason"] == "valence_enabled"
    assert status["user_facing_claims"] is True


def test_live_status_unknown_context_blocks_valence() -> None:
    status = build_valence_scoped_status(context="other_client", has_valence_model=True)
    assert status["enabled_for_context"] is False
    assert status["reason"] == "context_not_allowed"
    assert status["user_facing_claims"] is False


def test_live_semantic_positive_activation_internal_only() -> None:
    status = build_valence_scoped_status(context="internal_dashboard", has_valence_model=True)
    semantic = derive_semantic_state(
        activity_label="focused_cognitive_task",
        arousal_label="high",
        valence_label="positive",
        valence_status=status,
    )
    assert semantic["derived_state"] == "positive_activation"
    assert semantic["claim_level"] == "internal_only"


def test_live_semantic_unknown_when_activity_missing() -> None:
    status = build_valence_scoped_status(context="internal_dashboard", has_valence_model=False)
    semantic = derive_semantic_state(
        activity_label="",
        arousal_label="high",
        valence_label="neutral",
        valence_status=status,
    )
    assert semantic["activity_class"] == "unknown"
    assert semantic["derived_state"] == "uncertain_state"
    assert semantic["fallback_reason"] == "unknown_activity"
