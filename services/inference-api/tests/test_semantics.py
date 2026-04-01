from __future__ import annotations

from inference_api.models import ValenceScopedStatus
from inference_api.semantics import derive_semantic_state


def _status(*, context: str = "internal_dashboard", enabled: bool = True, reason: str = "valence_model_not_available") -> ValenceScopedStatus:
    return ValenceScopedStatus(
        mode="internal_scoped",
        context=context,
        enabled_for_context=enabled,
        user_facing_claims=False,
        risk_notifications=False,
        auto_personalization_trigger=False,
        reason=reason,
    )


def test_derive_semantic_state_calm_rest() -> None:
    semantic = derive_semantic_state(
        activity_label="seated_rest",
        arousal_label="low",
        valence_label="neutral",
        valence_status=_status(),
    )
    assert semantic["activity_class"] == "rest"
    assert semantic["derived_state"] == "calm_rest"
    assert semantic["claim_level"] in {"safe", "guarded"}


def test_derive_semantic_state_unknown_activity() -> None:
    semantic = derive_semantic_state(
        activity_label="unseen_label",
        arousal_label="low",
        valence_label="neutral",
        valence_status=_status(),
    )
    assert semantic["activity_class"] == "unknown"
    assert semantic["derived_state"] == "uncertain_state"
    assert semantic["fallback_reason"] == "unknown_activity"
    assert semantic["claim_level"] == "no_claim"


def test_derive_semantic_state_context_blocked_sets_fallback() -> None:
    semantic = derive_semantic_state(
        activity_label="walking",
        arousal_label="medium",
        valence_label="positive",
        valence_status=_status(enabled=False, context="public_app", reason="context_not_allowed"),
    )
    assert semantic["derived_state"] == "active_movement"
    assert semantic["fallback_reason"] == "valence_context_blocked"
