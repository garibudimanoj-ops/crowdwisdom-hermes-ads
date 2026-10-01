from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Shot(BaseModel):
    shot_id: str = Field(..., description="Unique identifier for the shot")
    start_seconds: float = Field(..., ge=0, description="Shot start time in seconds")
    end_seconds: float = Field(..., gt=0, description="Shot end time in seconds")
    duration_seconds: float = Field(..., gt=0, description="Shot duration in seconds")
    shot_type: Literal[
        "extreme_close_up",
        "close_up",
        "medium_shot",
        "wide_shot",
        "over_the_shoulder",
        "detail_shot",
        "screen_reflection",
        "environment_reveal",
    ] = Field(..., description="Type of camera shot")
    subject: str = Field(..., description="Primary subject of the shot")
    environment: str = Field(..., description="Environment/setting description")
    visual_description: str = Field(..., description="Detailed visual description")
    camera: str = Field(..., description="Camera setup description")
    camera_motion: str = Field(..., description="Camera movement description")
    lens_feel: str = Field(..., description="Lens characteristics and feel")
    composition: str = Field(..., description="Composition technique")
    depth: str = Field(..., description="Depth of field / layering description")
    lighting: str = Field(..., description="Lighting setup and mood")
    color_grade: str = Field(..., description="Color grading intention")
    mood: str = Field(..., description="Emotional mood of the shot")
    visual_events: list[str] = Field(default_factory=list, description="Key visual events in this shot")
    footage_queries: list[str] = Field(default_factory=list, description="Stock footage search queries")
    overlay_plan: str = Field(default="", description="Overlay graphics/text plan")
    transition_in: str = Field(default="", description="Transition entering this shot")
    transition_out: str = Field(default="", description="Transition leaving this shot")
    sound_design: str = Field(default="", description="Sound design notes for this shot")

    @model_validator(mode="after")
    def validate_timing(self) -> Shot:
        if self.end_seconds <= self.start_seconds:
            raise ValueError(f"Shot {self.shot_id}: end_seconds must be > start_seconds")
        expected_duration = round(self.end_seconds - self.start_seconds, 3)
        actual_duration = round(self.duration_seconds, 3)
        if abs(expected_duration - actual_duration) > 0.001:
            raise ValueError(f"Shot {self.shot_id}: duration_seconds ({actual_duration}) doesn't match end-start ({expected_duration})")
        return self


class ScenePlan(BaseModel):
    scene_id: int = Field(..., ge=1, le=5, description="Scene number 1-5")
    start_seconds: float = Field(..., ge=0, description="Scene start time in seconds")
    end_seconds: float = Field(..., gt=0, description="Scene end time in seconds")
    duration_seconds: float = Field(..., gt=0, description="Scene duration in seconds")
    creative_goal: str = Field(..., description="Creative objective for this scene")
    shots: list[Shot] = Field(..., min_length=1, description="Shots in this scene")
    sound_design: str = Field(..., description="Overall sound design for scene")
    continuity_notes: str = Field(default="", description="Continuity with adjacent scenes")
    compliance_notes: str = Field(default="", description="Compliance notes")
    risk_flags: list[str] = Field(default_factory=list, description="Risk flags")

    @model_validator(mode="after")
    def validate_scene_timing(self) -> ScenePlan:
        if self.end_seconds <= self.start_seconds:
            raise ValueError(f"Scene {self.scene_id}: end_seconds must be > start_seconds")
        expected = round(self.end_seconds - self.start_seconds, 3)
        actual = round(self.duration_seconds, 3)
        if abs(expected - actual) > 0.001:
            raise ValueError(f"Scene {self.scene_id}: duration mismatch ({actual} vs {expected})")
        # Shots must fit within scene boundaries
        for shot in self.shots:
            if shot.start_seconds < self.start_seconds - 0.001:
                raise ValueError(f"Scene {self.scene_id} shot {shot.shot_id}: starts before scene")
            if shot.end_seconds > self.end_seconds + 0.001:
                raise ValueError(f"Scene {self.scene_id} shot {shot.shot_id}: ends after scene")
        return self


class CinematographyPlan(BaseModel):
    campaign: str = Field(..., description="Campaign name")
    aspect_ratio: Literal["9:16"] = Field(default="9:16", description="Aspect ratio")
    width: int = Field(default=1080, description="Video width")
    height: int = Field(default=1920, description="Video height")
    fps: int = Field(default=30, description="Frames per second")
    total_duration_seconds: float = Field(default=45.0, description="Total duration")
    visual_style: str = Field(..., description="Overall visual style description")
    color_story: str = Field(..., description="Color story/progression")
    continuity_rules: list[str] = Field(default_factory=list, description="Continuity rules across scenes")
    scenes: list[ScenePlan] = Field(..., min_length=5, max_length=5, description="Exactly 5 scenes")

    @model_validator(mode="after")
    def validate_total_timing(self) -> CinematographyPlan:
        if len(self.scenes) != 5:
            raise ValueError(f"Must have exactly 5 scenes, got {len(self.scenes)}")

        expected_starts = [0, 8, 18, 28, 38]
        expected_ends = [8, 18, 28, 38, 45]

        for i, scene in enumerate(self.scenes):
            if scene.scene_id != i + 1:
                raise ValueError(f"Scene {i+1}: scene_id must be {i+1}, got {scene.scene_id}")
            if abs(scene.start_seconds - expected_starts[i]) > 0.001:
                raise ValueError(f"Scene {scene.scene_id}: start must be {expected_starts[i]}, got {scene.start_seconds}")
            if abs(scene.end_seconds - expected_ends[i]) > 0.001:
                raise ValueError(f"Scene {scene.scene_id}: end must be {expected_ends[i]}, got {scene.end_seconds}")

        total = round(sum(s.duration_seconds for s in self.scenes), 3)
        if abs(total - 45.0) > 0.001:
            raise ValueError(f"Total duration must be 45s, got {total}")

        return self


FORBIDDEN_CLAIMS = [
    "guaranteed profit",
    "guaranteed accuracy",
    "never lose",
    "beat the market",
    "90% confidence",
    "100% confidence",
    "predicts the future",
    "pre-validated order",
    "broker execution",
    "order confirmation",
    "blockchain",
    "cryptographic verification",
    "immutable record",
    "hash verification",
    "fake performance",
    "invented price",
    "fake trading result",
]


def validate_compliance(text: str) -> list[str]:
    """Check text for forbidden claims. Returns list of violations."""
    violations = []
    lower = text.lower()
    for claim in FORBIDDEN_CLAIMS:
        if claim in lower:
            violations.append(f"Forbidden claim detected: '{claim}'")
    return violations


def validate_plan_compliance(plan: CinematographyPlan) -> list[str]:
    """Validate entire plan for compliance violations."""
    violations = []
    for scene in plan.scenes:
        for shot in scene.shots:
            for field in ["visual_description", "camera_motion", "overlay_plan", "sound_design"]:
                val = getattr(shot, field, "")
                violations.extend(validate_compliance(val))
            violations.extend(validate_compliance(scene.sound_design))
            violations.extend(validate_compliance(scene.continuity_notes))
            violations.extend(validate_compliance(scene.compliance_notes))
    return violations