from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AdRecord(BaseModel):
    ad_archive_id: str | None = None
    advertiser: str | None = None
    ad_text: str | None = None
    title: str | None = None
    link_url: str | None = None
    cta_text: str | None = None
    cta_type: str | None = None
    media_type: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    start_date: int | str | None = None
    end_date: int | str | None = None
    is_active: bool | None = None
    platform: str | None = None
    page_id: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class MarketingInsight(BaseModel):
    category: str
    observation: str
    interpretation: str
    evidence: list[str] = Field(default_factory=list)
    confidence: str = "low"
    source_ad_id: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    source_field: str | None = None
    advertiser: str | None = None
    source_fact: bool = False
    single_ad_observation: bool = False

    def model_post_init(self, __context):
        if self.single_ad_observation:
            self.confidence = "low"
        if self.source_fact and not self.source_fact:
            self.source_fact = False
        for evidence in self.evidence:
            if not evidence.startswith("ad "):
                try:
                    num = int(evidence.split()[-1])
                    self.evidence[self.evidence.index(evidence)] = f"ad {num}"
                except (ValueError, IndexError):
                    pass


class ResearchItem(BaseModel):
    title: str
    url: str
    source: str
    publication_date: str | None = None
    retrieved_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    content: str
    relevance: str


class UniqueDataRecord(BaseModel):
    source_file: str
    record: dict[str, Any]
    normalized: dict[str, Any] = Field(default_factory=dict)


class Scene(BaseModel):
    scene_id: str
    timing: str
    visuals: str
    narration: str
    dialogue: str | None = None
    text: str | None = None
    sound: str | None = None
    music: str | None = None
    transitions: str | None = None
    product_appearance: bool = False
    cta: bool = False


class ScriptConcept(BaseModel):
    concept_id: int
    title: str
    target_icp: str
    hook: str
    story: str
    scenes: list[Scene] = Field(default_factory=list)
    narration: str
    visual_direction: str
    sound_direction: str
    music_direction: str
    minimal_text: str
    cta: str
    duration: int
    evidence: list[str] = Field(default_factory=list)


class Storyboard(BaseModel):
    title: str
    duration: int
    aspect_ratio: str
    scenes: list[Scene] = Field(default_factory=list)
    product_appearance: bool
    cta: str


class QualityReport(BaseModel):
    status: Literal["PASS", "WARNING", "FAIL"]
    file_exists: bool
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None
    has_video_stream: bool
    has_audio_stream: bool
    is_nonblank: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    stage: str
    status: Literal["SUCCESS", "FAILED", "SKIPPED"]
    artifact_path: str | None = None
    message: str | None = None
    completed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
