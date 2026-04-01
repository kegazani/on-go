from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi import Header

from inference_api.config import Settings
from inference_api.loader import LoadedBundle, load_model_bundle, predict
from inference_api.models import (
    PredictRequest,
    PredictResponse,
    ValenceCanaryDashboardResponse,
    ValenceScopedPolicyResponse,
    ValenceScopedStatus,
)
from inference_api.semantics import derive_semantic_state

logger = logging.getLogger(__name__)


def _default_valence_policy() -> dict[str, object]:
    return {
        "policy_id": "valence-scoped-policy-default-disabled",
        "mode": "disabled",
        "allowed_contexts": ["research_only"],
        "model": {"classifier_kind": "ridge_classifier", "confidence_threshold": 0.7},
        "guardrails": {
            "user_facing_claims": False,
            "risk_notifications": False,
            "auto_personalization_trigger": False,
        },
    }


def _load_valence_policy(path: str | None) -> tuple[dict[str, object], bool]:
    if not path:
        return _default_valence_policy(), False
    try:
        raw = json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        return _default_valence_policy(), False
    policy = _default_valence_policy()
    policy.update({k: v for k, v in raw.items() if k in policy or k in ("direction_rules", "rollback")})
    return policy, True


def _default_canary_state() -> dict[str, object]:
    return {
        "auto_disable": False,
        "effective_mode_override": None,
        "latest_check_utc": None,
        "alerts": [],
    }


def _load_canary_state(path: str | None) -> tuple[dict[str, object], bool]:
    if not path:
        return _default_canary_state(), False
    try:
        raw = json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        return _default_canary_state(), False
    state = _default_canary_state()
    state.update({k: v for k, v in raw.items() if k in state})
    return state, True


def _default_dashboard_snapshot() -> dict[str, object]:
    return {
        "snapshot_id": "valence-canary-snapshot-default",
        "generated_at_utc": None,
        "policy_mode": "disabled",
        "effective_mode": "disabled",
        "auto_disable": False,
        "status": "disabled",
        "alerts_count": 0,
        "latest_check_utc": None,
        "next_check_utc": None,
        "check_interval_minutes": 60,
        "alerts": [],
        "kpi_rollup": {"cycles_evaluated": 0, "triggers_evaluated": 0, "triggered_count": 0},
    }


def _load_dashboard_snapshot(path: str | None) -> tuple[dict[str, object], bool]:
    if not path:
        return _default_dashboard_snapshot(), False
    try:
        raw = json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        return _default_dashboard_snapshot(), False
    snapshot = _default_dashboard_snapshot()
    snapshot.update({k: v for k, v in raw.items() if k in snapshot})
    return snapshot, True


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_dashboard_fresh(snapshot: dict[str, object], freshness_slo_minutes: int) -> bool:
    generated = _parse_utc(snapshot.get("generated_at_utc"))
    if generated is None:
        return False
    age_minutes = (datetime.now(timezone.utc) - generated).total_seconds() / 60.0
    return age_minutes <= float(freshness_slo_minutes)


def _effective_mode(policy: dict[str, object], canary_state: dict[str, object]) -> str:
    override = canary_state.get("effective_mode_override")
    if isinstance(override, str) and override in {"disabled", "internal_scoped", "limited_production"}:
        return override
    if bool(canary_state.get("auto_disable", False)):
        return "disabled"
    return str(policy.get("mode", "disabled"))


def _resolve_valence_status(
    policy: dict[str, object],
    canary_state: dict[str, object],
    context: str,
    has_valence_model: bool,
) -> ValenceScopedStatus:
    mode = _effective_mode(policy=policy, canary_state=canary_state)
    allowed = [str(item) for item in policy.get("allowed_contexts", ["research_only"])]
    guardrails = policy.get("guardrails", {}) if isinstance(policy.get("guardrails"), dict) else {}
    user_facing_claims = bool(guardrails.get("user_facing_claims", False))
    risk_notifications = bool(guardrails.get("risk_notifications", False))
    auto_personalization_trigger = bool(guardrails.get("auto_personalization_trigger", False))

    if mode == "disabled":
        return ValenceScopedStatus(
            mode="disabled",
            context=context,
            enabled_for_context=False,
            user_facing_claims=user_facing_claims,
            risk_notifications=risk_notifications,
            auto_personalization_trigger=auto_personalization_trigger,
            reason="policy_disabled_or_auto_disabled",
        )
    if context not in allowed:
        return ValenceScopedStatus(
            mode="internal_scoped" if mode == "internal_scoped" else "limited_production",
            context=context,
            enabled_for_context=False,
            user_facing_claims=user_facing_claims,
            risk_notifications=risk_notifications,
            auto_personalization_trigger=auto_personalization_trigger,
            reason="context_not_allowed",
        )
    return ValenceScopedStatus(
        mode="internal_scoped" if mode == "internal_scoped" else "limited_production",
        context=context,
        enabled_for_context=True,
        user_facing_claims=user_facing_claims,
        risk_notifications=risk_notifications,
        auto_personalization_trigger=auto_personalization_trigger,
        reason="valence_enabled" if has_valence_model else "valence_model_not_available",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    app = FastAPI(
        title="On-Go Inference API",
        version="0.1.0",
        description="Online inference for activity/arousal predictions from feature vectors.",
    )

    model_bundle: LoadedBundle | None = None
    valence_policy: dict[str, object] = _default_valence_policy()
    valence_policy_loaded = False
    valence_canary_state: dict[str, object] = _default_canary_state()
    valence_canary_state_loaded = False
    valence_dashboard_snapshot: dict[str, object] = _default_dashboard_snapshot()
    valence_dashboard_snapshot_loaded = False

    @app.on_event("startup")
    def on_startup() -> None:
        nonlocal model_bundle, valence_policy, valence_policy_loaded
        nonlocal valence_canary_state, valence_canary_state_loaded
        nonlocal valence_dashboard_snapshot, valence_dashboard_snapshot_loaded
        if cfg.model_dir and cfg.model_dir.exists():
            model_bundle = load_model_bundle(cfg.model_dir)
        valence_policy, valence_policy_loaded = _load_valence_policy(
            str(cfg.valence_scoped_policy_path) if cfg.valence_scoped_policy_path else None
        )
        valence_canary_state, valence_canary_state_loaded = _load_canary_state(
            str(cfg.valence_canary_state_path) if cfg.valence_canary_state_path else None
        )
        valence_dashboard_snapshot, valence_dashboard_snapshot_loaded = _load_dashboard_snapshot(
            str(cfg.valence_dashboard_snapshot_path) if cfg.valence_dashboard_snapshot_path else None
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        loaded = model_bundle is not None
        dashboard_fresh = _is_dashboard_fresh(
            snapshot=valence_dashboard_snapshot,
            freshness_slo_minutes=cfg.valence_dashboard_freshness_slo_minutes,
        )
        return {
            "status": "ok",
            "model_loaded": str(loaded).lower(),
            "valence_policy_loaded": str(valence_policy_loaded).lower(),
            "valence_canary_state_loaded": str(valence_canary_state_loaded).lower(),
            "valence_dashboard_snapshot_loaded": str(valence_dashboard_snapshot_loaded).lower(),
            "valence_dashboard_fresh": str(dashboard_fresh).lower(),
            "valence_mode": _effective_mode(policy=valence_policy, canary_state=valence_canary_state),
            "valence_auto_disable": str(bool(valence_canary_state.get("auto_disable", False))).lower(),
        }

    @app.get("/v1/policy/valence-scoped", response_model=ValenceScopedPolicyResponse)
    async def valence_scoped_policy() -> ValenceScopedPolicyResponse:
        model_block = valence_policy.get("model", {}) if isinstance(valence_policy.get("model"), dict) else {}
        alerts = valence_canary_state.get("alerts", [])
        return ValenceScopedPolicyResponse(
            loaded=valence_policy_loaded,
            mode=str(valence_policy.get("mode", "disabled")),
            effective_mode=_effective_mode(policy=valence_policy, canary_state=valence_canary_state),
            policy_id=str(valence_policy.get("policy_id", "valence-scoped-policy-default-disabled")),
            allowed_contexts=[str(item) for item in valence_policy.get("allowed_contexts", ["research_only"])],
            classifier_kind=str(model_block.get("classifier_kind", "ridge_classifier")),
            confidence_threshold=float(model_block.get("confidence_threshold", 0.7)),
            auto_disable=bool(valence_canary_state.get("auto_disable", False)),
            latest_check_utc=str(valence_canary_state.get("latest_check_utc")) if valence_canary_state.get("latest_check_utc") else None,
            alerts=[str(item) for item in alerts] if isinstance(alerts, list) else [],
        )

    @app.get("/v1/monitoring/valence-canary", response_model=ValenceCanaryDashboardResponse)
    async def valence_canary_dashboard() -> ValenceCanaryDashboardResponse:
        return ValenceCanaryDashboardResponse(
            loaded=valence_dashboard_snapshot_loaded,
            freshness_slo_minutes=cfg.valence_dashboard_freshness_slo_minutes,
            is_fresh=_is_dashboard_fresh(
                snapshot=valence_dashboard_snapshot,
                freshness_slo_minutes=cfg.valence_dashboard_freshness_slo_minutes,
            ),
            snapshot=valence_dashboard_snapshot,
        )

    @app.post("/v1/predict", response_model=PredictResponse)
    async def predict_endpoint(
        payload: PredictRequest,
        x_on_go_context: str = Header(default="research_only", alias="X-On-Go-Context"),
    ) -> PredictResponse:
        if model_bundle is None:
            raise HTTPException(status_code=503, detail="model not loaded")
        try:
            result = predict(bundle=model_bundle, feature_vector=payload.feature_vector)
            valence_scoped_status = _resolve_valence_status(
                policy=valence_policy,
                canary_state=valence_canary_state,
                context=x_on_go_context,
                has_valence_model=model_bundle.valence_coarse is not None,
            )
            semantic = derive_semantic_state(
                activity_label=str(result.get("activity", "")),
                arousal_label=str(result.get("arousal_coarse", "")),
                valence_label=str(result.get("valence_coarse", "")),
                valence_status=valence_scoped_status,
            )
            out = PredictResponse(
                activity=str(result.get("activity", "")),
                activity_class=str(semantic["activity_class"]),
                arousal_coarse=str(semantic["arousal_coarse"]),
                valence_coarse=str(semantic["valence_coarse"]),
                valence_scoped_status=valence_scoped_status,
                derived_state=str(semantic["derived_state"]),
                confidence=semantic["confidence"],
                fallback_reason=str(semantic["fallback_reason"]),
                claim_level=str(semantic["claim_level"]),
            )
            logger.info(
                "predict outbound %s",
                json.dumps(out.model_dump(mode="json"), default=str),
            )
            return out
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

    return app
