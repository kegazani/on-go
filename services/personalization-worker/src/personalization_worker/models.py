from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AdaptationState(BaseModel):
    global_model_reference: str = ""
    active_personalization_level: str = "none"
    last_calibrated_at_utc: Optional[str] = None


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
