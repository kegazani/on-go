from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DatasetRecord(BaseModel):
    dataset_id: str
    dataset_version: str
    source: str
    source_uri: Optional[str] = None
    source_license: Optional[str] = None
    ingestion_script_version: str
    preprocessing_version: str
    split_strategy: str
    target_tracks: list[str] = Field(default_factory=list)
    labels_available: list[str] = Field(default_factory=list)
    modalities_available: list[str] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    subject_count: int = Field(default=0, ge=0)
    session_count: int = Field(default=0, ge=0)
    created_at_utc: datetime
    metadata_object: str


class UnifiedSubject(BaseModel):
    subject_id: str
    source_subject_id: str
    dataset_id: str
    dataset_version: str


class UnifiedSession(BaseModel):
    session_id: str
    subject_id: str
    dataset_id: str
    dataset_version: str
    session_type: Literal["external_dataset"] = "external_dataset"


class UnifiedSegmentLabel(BaseModel):
    dataset_id: str
    dataset_version: str
    session_id: str
    segment_id: str
    source_label: str
    source_label_value: str
    activity_label: str
    activity_group: str
    arousal_score: int = Field(ge=1, le=9)
    valence_score: int = Field(ge=1, le=9)
    confidence: float = Field(ge=0.0, le=1.0)
    source_segment_start_index: Optional[int] = Field(default=None, ge=0)
    source_segment_end_index: Optional[int] = Field(default=None, ge=0)
    source_sample_count: Optional[int] = Field(default=None, ge=1)
    source: str = "dataset_mapping"


class SplitManifest(BaseModel):
    dataset_id: str
    dataset_version: str
    strategy: str
    train_subject_ids: list[str] = Field(default_factory=list)
    validation_subject_ids: list[str] = Field(default_factory=list)
    test_subject_ids: list[str] = Field(default_factory=list)
