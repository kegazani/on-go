from __future__ import annotations

from typing import Literal
from typing import Optional

from pydantic import BaseModel


class PredictRequest(BaseModel):
    feature_vector: dict[str, float]


class ValenceScopedStatus(BaseModel):
    mode: Literal["disabled", "internal_scoped", "limited_production"]
    context: str
    enabled_for_context: bool
    user_facing_claims: bool
    risk_notifications: bool
    auto_personalization_trigger: bool
    reason: str


class SemanticConfidence(BaseModel):
    score: float | None
    band: Literal["high", "medium", "low", "insufficient"]


class PredictResponse(BaseModel):
    activity: str
    activity_class: Literal["rest", "recovery", "movement", "physical_load", "cognitive", "mixed", "unknown"]
    arousal_coarse: str
    valence_coarse: Literal["negative", "neutral", "positive", "unknown"]
    valence_scoped_status: ValenceScopedStatus
    derived_state: Literal[
        "calm_rest",
        "active_movement",
        "physical_load",
        "possible_stress",
        "positive_activation",
        "negative_activation",
        "uncertain_state",
    ]
    confidence: SemanticConfidence
    fallback_reason: Literal[
        "none",
        "insufficient_signal",
        "low_confidence",
        "unknown_activity",
        "unknown_arousal",
        "contradictory_signals",
        "valence_policy_disabled",
        "valence_context_blocked",
        "valence_auto_disabled",
        "valence_low_confidence",
    ]
    claim_level: Literal["safe", "guarded", "internal_only", "no_claim"]


class ValenceScopedPolicyResponse(BaseModel):
    loaded: bool
    mode: Literal["disabled", "internal_scoped", "limited_production"]
    effective_mode: Literal["disabled", "internal_scoped", "limited_production"]
    policy_id: str
    allowed_contexts: list[str]
    classifier_kind: str
    confidence_threshold: float
    auto_disable: bool
    latest_check_utc: Optional[str]
    alerts: list[str]


class ValenceCanaryDashboardResponse(BaseModel):
    loaded: bool
    freshness_slo_minutes: int
    is_fresh: bool
    snapshot: dict[str, object]
