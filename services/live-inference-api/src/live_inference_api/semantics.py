from __future__ import annotations

_REST_LABELS = {"seated_rest", "standing_rest", "baseline", "rest", "stationary", "idle"}
_RECOVERY_LABELS = {"recovery_rest", "recovery"}
_MOVEMENT_LABELS = {"walking", "stairs", "light_exercise", "movement"}
_PHYSICAL_LOAD_LABELS = {"vigorous_exercise", "physical_load", "exercise"}
_COGNITIVE_LABELS = {"focused_cognitive_task", "cognitive", "stress_task"}
_MIXED_LABELS = {"mixed_transition", "mixed"}

_ALLOWED_CONTEXTS = {"research_only", "internal_dashboard", "shadow_mode", "public_app"}


def build_valence_scoped_status(*, context: str, has_valence_model: bool) -> dict[str, object]:
    mode = "internal_scoped"
    enabled = context in _ALLOWED_CONTEXTS
    if not enabled:
        reason = "context_not_allowed"
    elif has_valence_model:
        reason = "valence_enabled"
    else:
        reason = "valence_model_not_available"
    user_facing_claims = bool(enabled and has_valence_model and context == "public_app")
    return {
        "mode": mode,
        "context": context,
        "enabled_for_context": enabled,
        "user_facing_claims": user_facing_claims,
        "risk_notifications": False,
        "auto_personalization_trigger": False,
        "reason": reason,
    }


def normalize_activity_class(activity_label: str) -> str:
    label = str(activity_label or "").strip().lower()
    if label in _REST_LABELS:
        return "rest"
    if label in _RECOVERY_LABELS:
        return "recovery"
    if label in _MOVEMENT_LABELS:
        return "movement"
    if label in _PHYSICAL_LOAD_LABELS:
        return "physical_load"
    if label in _COGNITIVE_LABELS:
        return "cognitive"
    if label in _MIXED_LABELS:
        return "mixed"
    if label in {"unknown", ""}:
        return "unknown"
    return "unknown"


def normalize_arousal_coarse(arousal_label: str) -> str:
    label = str(arousal_label or "").strip().lower()
    if label in {"low", "medium", "high"}:
        return label
    return "unknown"


def normalize_valence_coarse(valence_label: str, status: dict[str, object]) -> str:
    if not bool(status.get("enabled_for_context", False)):
        return "unknown"
    label = str(valence_label or "").strip().lower()
    if label in {"negative", "neutral", "positive"}:
        return label
    return "unknown"


def _map_status_reason_to_fallback(status: dict[str, object]) -> str | None:
    reason = str(status.get("reason", ""))
    if reason == "context_not_allowed":
        return "valence_context_blocked"
    if reason == "valence_model_not_available":
        return "valence_low_confidence"
    return None


def _build_confidence(derived_state: str, fallback_reason: str) -> dict[str, object]:
    score = 0.35
    if derived_state in {"calm_rest", "active_movement", "physical_load"}:
        score = 0.85
    elif derived_state == "possible_stress":
        score = 0.7
    elif derived_state in {"positive_activation", "negative_activation"}:
        score = 0.6
    elif fallback_reason in {"unknown_activity", "unknown_arousal", "contradictory_signals"}:
        score = 0.2
    elif fallback_reason in {"insufficient_signal", "low_confidence"}:
        score = 0.35

    if score >= 0.8:
        band = "high"
    elif score >= 0.6:
        band = "medium"
    elif score >= 0.4:
        band = "low"
    else:
        band = "insufficient"
    return {"score": round(score, 3), "band": band}


def derive_semantic_state(
    *,
    activity_label: str,
    arousal_label: str,
    valence_label: str,
    valence_status: dict[str, object],
) -> dict[str, object]:
    activity_class = normalize_activity_class(activity_label)
    arousal_coarse = normalize_arousal_coarse(arousal_label)
    valence_coarse = normalize_valence_coarse(valence_label, valence_status)

    derived_state = "uncertain_state"
    claim_level = "no_claim"
    fallback_reason = "contradictory_signals"

    if activity_class == "unknown":
        fallback_reason = "unknown_activity"
    elif arousal_coarse == "unknown":
        fallback_reason = "unknown_arousal"
    elif activity_class == "mixed":
        fallback_reason = "insufficient_signal"
    elif activity_class in {"rest", "recovery"} and arousal_coarse == "low":
        derived_state = "calm_rest"
        claim_level = "safe"
        fallback_reason = "none"
    elif activity_class == "movement" and arousal_coarse in {"low", "medium"}:
        derived_state = "active_movement"
        claim_level = "safe"
        fallback_reason = "none"
    elif activity_class == "physical_load" and arousal_coarse in {"medium", "high"}:
        derived_state = "physical_load"
        claim_level = "safe"
        fallback_reason = "none"
    elif activity_class in {"rest", "recovery", "cognitive"} and arousal_coarse == "high" and valence_coarse in {"unknown", "neutral"}:
        derived_state = "possible_stress"
        claim_level = "guarded"
        fallback_reason = "none"
    elif arousal_coarse == "high" and valence_coarse == "positive" and bool(valence_status.get("enabled_for_context", False)):
        derived_state = "positive_activation"
        claim_level = "internal_only"
        fallback_reason = "none"
    elif arousal_coarse == "high" and valence_coarse == "negative" and bool(valence_status.get("enabled_for_context", False)):
        derived_state = "negative_activation"
        claim_level = "internal_only"
        fallback_reason = "none"

    policy_fallback = _map_status_reason_to_fallback(valence_status)
    if policy_fallback and fallback_reason == "none":
        fallback_reason = policy_fallback

    confidence = _build_confidence(derived_state=derived_state, fallback_reason=fallback_reason)
    if confidence["band"] in {"low", "insufficient"} and claim_level == "safe":
        claim_level = "guarded"
        if fallback_reason == "none":
            fallback_reason = "low_confidence"

    return {
        "activity_class": activity_class,
        "arousal_coarse": arousal_coarse,
        "valence_coarse": valence_coarse,
        "derived_state": derived_state,
        "confidence": confidence,
        "fallback_reason": fallback_reason,
        "claim_level": claim_level,
    }
