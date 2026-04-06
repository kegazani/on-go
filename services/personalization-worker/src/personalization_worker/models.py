from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class L2CalibrationState(BaseModel):
    version: str = "per-l2-v1"
    output_label_maps: dict[str, dict[str, str]] = Field(default_factory=dict)
    global_model_reference_match: Optional[str] = None


class AdaptationState(BaseModel):
    global_model_reference: str = ""
    active_personalization_level: str = "none"
    last_calibrated_at_utc: Optional[str] = None
    l2_calibration: Optional[L2CalibrationState] = None


class ProfileCreate(BaseModel):
    subject_id: str = Field(min_length=1)
    physiology_baseline: dict[str, Any]
    adaptation_state: AdaptationState = Field(default_factory=lambda: AdaptationState())
    notes: Optional[str] = None


class ProfileResponse(BaseModel):
    subject_id: str
    physiology_baseline: dict[str, Any]
    adaptation_state: AdaptationState
    created_at_utc: str
    updated_at_utc: str
    notes: Optional[str] = None


class L2CalibrationPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_label_maps: Optional[dict[str, dict[str, str]]] = None
    version: Optional[str] = None
    global_model_reference_match: Optional[str] = None
    active_personalization_level: Optional[str] = None
    global_model_reference: Optional[str] = None
    last_calibrated_at_utc: Optional[str] = None


def merge_l2_calibration_patch(
    profile: ProfileResponse,
    patch: L2CalibrationPatchBody,
) -> ProfileCreate:
    data = profile.model_dump()
    adapt = data["adaptation_state"]
    pdata = patch.model_dump(exclude_unset=True)
    if "active_personalization_level" in pdata:
        adapt["active_personalization_level"] = pdata["active_personalization_level"]
    if "global_model_reference" in pdata:
        adapt["global_model_reference"] = pdata["global_model_reference"]
    if "last_calibrated_at_utc" in pdata:
        adapt["last_calibrated_at_utc"] = pdata["last_calibrated_at_utc"]
    l2_touch = any(
        k in pdata
        for k in ("output_label_maps", "version", "global_model_reference_match")
    )
    if l2_touch:
        l2_raw = adapt.get("l2_calibration")
        if l2_raw is None:
            l2_raw = {"version": "per-l2-v1", "output_label_maps": {}, "global_model_reference_match": None}
        maps = {k: dict(v) for k, v in (l2_raw.get("output_label_maps") or {}).items()}
        if pdata.get("output_label_maps"):
            for track, tm in pdata["output_label_maps"].items():
                cur = dict(maps.get(track) or {})
                cur.update(tm)
                maps[track] = cur
        ver = l2_raw.get("version", "per-l2-v1")
        if "version" in pdata and pdata["version"] is not None:
            ver = pdata["version"]
        gmatch = l2_raw.get("global_model_reference_match")
        if "global_model_reference_match" in pdata:
            gmatch = pdata["global_model_reference_match"]
        adapt["l2_calibration"] = {
            "version": ver,
            "output_label_maps": maps,
            "global_model_reference_match": gmatch,
        }
    return ProfileCreate(
        subject_id=profile.subject_id,
        physiology_baseline=profile.physiology_baseline,
        adaptation_state=AdaptationState(**adapt),
        notes=profile.notes,
    )
