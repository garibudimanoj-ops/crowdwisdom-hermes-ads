"""Pipeline orchestrator for the CrowdWisdom Hermes ads pipeline.

Executes stages in deterministic order with proper block propagation.
Records stage state and persists a run manifest.

Stages (in order):
    ads           → fetch and normalize Meta Ads Library ads
    marketing     → extract insights: hooks, pain points, ICPs, CTAs
    research      → search and compile research findings
    data          → validate CrowdWisdom data availability
    script        → generate 3 video-ad concepts via Hermes
    creative_dir  → review concepts, select direction, build storyboard
    storyboard    → assemble final storyboard from selected concept
    video         → render video via OpenMontage
    quality       → validate video quality and storyboard consistency
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from src.agents.ads_manager import AdsManager, AdsManagerError
from src.agents.marketing_analyzer import MarketingAnalyzer
from src.agents.research_agent import ResearchAgent
from src.agents.data_agent import DataAgent
from src.agents.script_agent import ScriptAgent, ScriptAgentError
from src.agents.video_agent import run_video_agent, VideoAgentError
from src.agents.quality_agent import run_quality_agent
from src.integrations.hermes_runner import HermesError as HermesRunnerError
from src.status.pipeline_status import get_pipeline_status

ERROR_CATEGORY_NONE = "none"
ERROR_CATEGORY_HERMES = "hermes"
ERROR_CATEGORY_OPENMONTAGE = "openmontage"
ERROR_CATEGORY_VALIDATION = "validation"


class PipelineStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineManifest:
    execution_mode: str
    started_at: str
    completed_at: str | None = None
    overall_status: PipelineStatus = PipelineStatus.PENDING
    stages: list[dict[str, Any]] = None
    output_paths: dict[str, str] = None
    errors: dict[str, dict[str, Any]] = None
    blockers: list[str] = None

    def __post_init__(self) -> None:
        if self.stages is None:
            self.stages = []
        if self.output_paths is None:
            self.output_paths = {}
        if self.errors is None:
            self.errors = {}
        if self.blockers is None:
            self.blockers = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "overall_status": self.overall_status.value,
            "stages": self.stages,
            "output_paths": self.output_paths,
            "errors": self.errors,
            "blockers": self.blockers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineManifest:
        return cls(
            execution_mode=data.get("execution_mode", "live"),
            started_at=data.get("started_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
            overall_status=PipelineStatus(data.get("overall_status", "pending")),
            stages=data.get("stages", []),
            output_paths=data.get("output_paths", {}),
            errors=data.get("errors", {}),
            blockers=data.get("blockers", []),
        )


class Orchestrator:
    """Pipeline stage orchestrator with block propagation."""

    # Stage ordering and dependencies
    STAGE_ORDER = [
        "ads",
        "marketing",
        "research",
        "data",
        "script",
        "creative_dir",
        "storyboard",
        "video",
        "quality",
    ]

    # Stages that must complete before these
    STAGE_DEPS = {
        "marketing": ["ads"],
        "research": ["marketing"],
        "data": ["research"],
        "script": ["data"],
        "creative_dir": ["script"],
        "storyboard": ["creative_dir"],
        "video": ["storyboard"],
        "quality": ["video"],
    }

    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or os.environ.get("PIPELINE_MODE", "live")
        self.manifest = PipelineManifest(execution_mode=self.mode, started_at=datetime.now(timezone.utc).isoformat())
        self.stage_results: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Stage execution helpers
    # ------------------------------------------------------------------

    def _stage_started(self, stage: str) -> None:
        self.manifest.stages.append(
            {
                "stage": stage,
                "status": PipelineStatus.RUNNING.value,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "outputs": None,
                "error": None,
            }
        )
        self.stage_results[stage] = {
            "status": PipelineStatus.RUNNING,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "outputs": None,
            "error": None,
        }

    def _stage_completed(
        self,
        stage: str,
        status: PipelineStatus,
        outputs: dict[str, str] | None,
        error: dict[str, Any] | None,
    ) -> None:
        # Update last stage entry
        if self.manifest.stages and self.manifest.stages[-1]["stage"] == stage:
            self.manifest.stages[-1].update(
                {
                    "status": status.value,
                    "started_at": self.manifest.stages[-1].get("started_at"),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "outputs": outputs,
                    "error": error,
                }
            )
        else:
            # Find or append
            for s in reversed(self.manifest.stages):
                if s["stage"] == stage:
                    s.update(
                        {
                            "status": status.value,
                            "started_at": s.get("started_at"),
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "outputs": outputs,
                            "error": error,
                        }
                    )
                    break

        self.stage_results[stage] = {
            "status": status,
            "started_at": self.stage_results.get(stage, {}).get("started_at"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "outputs": outputs,
            "error": error,
        }

    def _stage_blocked(self, stage: str, reason: str) -> None:
        self._stage_completed(stage, PipelineStatus.BLOCKED, None, {"reason": reason})

    # ------------------------------------------------------------------
    # Block propagation
    # ------------------------------------------------------------------

    def _propagate_block(self, failed_stage: str, reason: str) -> bool:
        """Block all downstream stages of failed_stage.

        Returns True if any downstream was already completed (should not happen
        in correct flow, but we conservatively skip them).
        """
        blocked = []
        for downstream in self.STAGE_ORDER:
            if downstream == failed_stage:
                break
            if downstream in self.STAGE_DEPS:
                deps = self.STAGE_DEPS[downstream]
                if any(d == failed_stage for d in deps):
                    # Check if this downstream is already completed
                    if downstream in self.stage_results:
                        if self.stage_results[downstream]["status"] == PipelineStatus.COMPLETED:
                            # Already completed — keep it completed but add blocker note
                            blocked.append(downstream)
                            continue
                    # Block this stage
                    self._stage_blocked(downstream, f"{failed_stage} failed/blocked: {reason}")
                    blocked.append(downstream)
            elif downstream in self.STAGE_DEPS.get("creative_dir", []):
                # Already handled via dict
                pass
        return blocked

    # ------------------------------------------------------------------
    # Run each stage
    # ------------------------------------------------------------------

    def run_ads(self) -> dict[str, Any]:
        """Run the Ads stage."""
        self._stage_started("ads")
        if self.mode == "dry_run":
            outputs = {"ads_json": "outputs/ads/ads.json", "note": "dry_run"}
            self._stage_completed("ads", PipelineStatus.COMPLETED, outputs, {"mode": "dry_run"})
            return {"status": "completed", "outputs": outputs, "mode": "dry_run"}
        try:
            ads_mgr = AdsManager()
            ads_data = ads_mgr.run()
            outputs = {"ads_json": str(ads_mgr.output_path)}
            self._stage_completed("ads", PipelineStatus.COMPLETED, outputs, None)
            return {"status": "completed", "outputs": outputs}
        except Exception as exc:
            self._stage_completed("ads", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}

    def run_marketing(self) -> dict[str, Any]:
        """Run the Marketing Analyzer stage."""
        self._stage_started("marketing")
        if self.mode == "dry_run":
            outputs = {"insights_json": "outputs/insights/marketing_insights.json", "note": "dry_run"}
            self._stage_completed("marketing", PipelineStatus.COMPLETED, outputs, {"mode": "dry_run"})
            return {"status": "completed", "outputs": outputs, "mode": "dry_run"}
        try:
            # Must have ads output
            ads_path = Path("outputs/ads/ads.json")
            if not ads_path.exists():
                raise FileNotFoundError("ads.json not found — run ads stage first.")

            mktg = MarketingAnalyzer()
            insights_data = mktg.run()
            outputs = {"insights_json": str(ads_path.parent / "marketing_insights.json")}
            self._stage_completed("marketing", PipelineStatus.COMPLETED, outputs, None)
            return {"status": "completed", "outputs": outputs}
        except Exception as exc:
            self._stage_completed("marketing", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}

    def run_research(self) -> dict[str, Any]:
        """Run the Research stage."""
        self._stage_started("research")
        if self.mode == "dry_run":
            outputs = {"research_json": "outputs/research/research.json", "note": "dry_run"}
            self._stage_completed("research", PipelineStatus.COMPLETED, outputs, {"mode": "dry_run"})
            return {"status": "completed", "outputs": outputs, "mode": "dry_run"}
        try:
            research = ResearchAgent()
            research_data = research.run()
            outputs = {"research_json": "outputs/research/research.json"}
            self._stage_completed("research", PipelineStatus.COMPLETED, outputs, None)
            return {"status": "completed", "outputs": outputs}
        except Exception as exc:
            self._stage_completed("research", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}

    def run_data(self) -> dict[str, Any]:
        """Run the Data Agent stage."""
        self._stage_started("data")
        if self.mode == "dry_run":
            outputs = {"unique_data_json": "data/processed/unique_data.json", "note": "dry_run"}
            self._stage_completed("data", PipelineStatus.COMPLETED, outputs, {"mode": "dry_run"})
            return {"status": "completed", "outputs": outputs, "mode": "dry_run"}
        try:
            data = DataAgent()
            data_result = data.run()
            unique_data_available = data_result.get("unique_data_available", False)
            outputs = {
                "unique_data_json": "data/processed/unique_data.json",
                "unique_data_available": unique_data_available,
            }
            self._stage_completed("data", PipelineStatus.COMPLETED, outputs, None)
            return {"status": "completed", "outputs": outputs}
        except Exception as exc:
            self._stage_completed("data", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}

    def run_script(self) -> dict[str, Any]:
        """Run the Script Agent stage.

        This is the stage that can be BLOCKED by Hermes/OpenRouter HTTP 429.
        In live mode with rate limit, we mark it BLOCKED (not FAILED) so that
        downstream stages also become BLOCKED but can resume when the quota resets.
        In dry_run mode, we exercise the stage using fixtures.
        """
        self._stage_started("script")

        # Check mode
        if self.mode == "dry_run":
            # Exercise using a fixture approach — but we must NOT create fake concepts.
            # For dry-run, we mark the script stage as completed with a fixture marker.
            # The downstream stages (creative_dir, etc.) will also exercise using
            # the dry-run fixtures they consume.
            self._stage_completed(
                "script",
                PipelineStatus.COMPLETED,
                {"note": "dry_run: script stage exercised via fixtures"},
                {"mode": "dry_run", "note": "dry_run fixture exercised"},
            )
            return {
                "status": "completed",
                "outputs": {"note": "dry_run: script stage exercised via fixtures"},
                "mode": "dry_run",
            }

        # Live mode: try Hermes
        try:
            # Determine unique_data_available:
            # 1. First check in-memory data-stage result
            data_stage_result = self.stage_results.get("data", {})
            unique_data_available = data_stage_result.get("outputs", {}).get(
                "unique_data_available", None
            )

            # 2. If no in-memory result (standalone execution), fall back to
            #    reading the processed artifact directly.
            if unique_data_available is None:
                processed_path = Path("data/processed/unique_data.json")
                if processed_path.exists():
                    try:
                        with processed_path.open("r", encoding="utf-8") as f:
                            processed = json.load(f)
                        # Safely interpret the processed artifact's status
                        status = processed.get("metadata", {}).get("status", "")
                        if status == "no_data_available":
                            unique_data_available = False
                        else:
                            unique_data_available = processed.get("unique_data_available", True)
                    except (json.JSONDecodeError, OSError):
                        unique_data_available = True
                else:
                    unique_data_available = True

            script_agent = ScriptAgent()
            result = script_agent.run()

            # If unique data is not available, Concept 2 is BLOCKED
            if not unique_data_available:
                concept_2_path = script_agent.output_dir / "concept_2.json"
                if concept_2_path.exists():
                    with concept_2_path.open("r", encoding="utf-8") as f:
                        concept_2_data = json.load(f)
                    # Add explicit blocked metadata (nested only — no top-level)
                    concept_2_data.setdefault("concept", {}).setdefault(
                        "limitations",
                        ["Unique CrowdWisdom data is not available"],
                    )
                    with concept_2_path.open("w", encoding="utf-8") as f:
                        json.dump(concept_2_data, f, indent=2, ensure_ascii=False)

            outputs = {
                "concept_1": script_agent.output_dir / "concept_1.json",
                "concept_2": script_agent.output_dir / "concept_2.json",
                "concept_3": script_agent.output_dir / "concept_3.json",
            }
            # Only record outputs if files actually exist
            real_outputs = {}
            for k, v in outputs.items():
                if v.exists():
                    real_outputs[k] = str(v)
            # Record blocked/viable concepts
            if not unique_data_available:
                real_outputs["blocked_concepts"] = ["concept_2"]
                real_outputs["viable_concepts"] = ["concept_1", "concept_3"]
            self._stage_completed(
                "script",
                PipelineStatus.COMPLETED,
                real_outputs if real_outputs else None,
                None,
            )
            return {"status": "completed", "outputs": real_outputs}
        except HermesRunnerError as exc:
            # OpenRouter 429 or other Hermes error → BLOCK, not fail
            self._stage_blocked("script", f"Hermes/OpenRouter error: {exc}")
            return {"status": "blocked", "error": str(exc)}
        except ScriptAgentError as exc:
            # Script generation failed (other error) → FAIL
            self._stage_completed("script", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}
        except Exception as exc:
            self._stage_blocked("script", f"Unexpected error: {exc}")
            return {"status": "blocked", "error": str(exc)}

    def run_creative_dir(self) -> dict[str, Any]:
        """Run the Creative Director stage."""
        self._stage_started("creative_dir")
        # If script is blocked, creative director is also blocked
        if self.mode == "dry_run":
            self._stage_completed(
                "creative_dir",
                PipelineStatus.COMPLETED,
                {"note": "dry_run: creative director exercised via fixtures"},
                {"mode": "dry_run"},
            )
            return {"status": "completed", "mode": "dry_run"}

        # Live mode: determine if we can proceed with Creative Director.
        # Strategy:
        # 1. If we have an in-memory script result with status COMPLETED, proceed.
        # 2. If we have no useful in-memory result (empty or status != COMPLETED),
        #    fall back to checking concept artifacts on disk.
        # 3. If script stage not completed at all, block.
        script_result = self.stage_results.get("script")

        # Check if in-memory script result is COMPLETED
        script_completed = (
            script_result is not None
            and isinstance(script_result, dict)
            and script_result.get("status") == PipelineStatus.COMPLETED
        )

        if script_completed:
            # In-memory result present and complete → proceed normally
            try:
                from src.agents.creative_director import CreativeDirector

                director = CreativeDirector()
                summary = director.run()
                outputs = {"creative_review": "outputs/creative_review.json"}
                self._stage_completed("creative_dir", PipelineStatus.COMPLETED, outputs, None)
                return {"status": "completed", "outputs": outputs}
            except Exception as exc:
                self._stage_completed("creative_dir", PipelineStatus.FAILED, None, {"error": str(exc)})
                return {"status": "failed", "error": str(exc)}

        # No useful in-memory script result (empty dict, missing, or status != COMPLETED).
        # Fall back to checking concept artifacts on disk for standalone execution.
        scripts_dir = Path("outputs/scripts")
        required_files = [
            scripts_dir / "concept_1.json",
            scripts_dir / "concept_2.json",
            scripts_dir / "concept_3.json",
        ]
        all_exist = all(f.exists() for f in required_files)

        if all_exist:
            all_valid_json = True
            for f in required_files:
                try:
                    with f.open("r", encoding="utf-8") as fh:
                        json.load(fh)
                except (json.JSONDecodeError, OSError):
                    all_valid_json = False
                    break
            if all_valid_json:
                try:
                    from src.agents.creative_director import CreativeDirector

                    director = CreativeDirector()
                    summary = director.run()
                    outputs = {"creative_review": "outputs/creative_review.json"}
                    self._stage_completed("creative_dir", PipelineStatus.COMPLETED, outputs, None)
                    return {"status": "completed", "outputs": outputs}
                except Exception as exc:
                    self._stage_completed("creative_dir", PipelineStatus.FAILED, None, {"error": str(exc)})
                    return {"status": "failed", "error": str(exc)}
            else:
                self._stage_blocked(
                    "creative_dir",
                    "script stage artifacts malformed: concept JSON invalid",
                )
                return {
                    "status": "blocked",
                    "reason": "script stage artifacts malformed",
                }
        else:
            self._stage_blocked(
                "creative_dir",
                "script stage artifacts incomplete: missing concept files",
            )
            return {
                "status": "blocked",
                "reason": "script stage artifacts incomplete",
            }

        # Should not reach here, but fallback block
        self._stage_blocked(
            "creative_dir",
            "script stage not completed and no disk artifacts found",
        )
        return {
            "status": "blocked",
            "reason": "script stage not completed",
        }

    def run_storyboard(self) -> dict[str, Any]:
        """Run the Storyboard stage."""
        self._stage_started("storyboard")
        # If creative_dir is blocked, storyboard is blocked
        creative_result = self.stage_results.get("creative_dir", {})
        if creative_result.get("status") != PipelineStatus.COMPLETED:
            self._stage_blocked(
                "storyboard",
                f"creative_dir stage not completed (status={creative_result.get('status')})",
            )
            return {"status": "blocked", "reason": "creative_dir stage not completed"}

        if self.mode == "dry_run":
            self._stage_completed(
                "storyboard",
                PipelineStatus.COMPLETED,
                {"note": "dry_run: storyboard exercised via fixtures"},
                {"mode": "dry_run"},
            )
            return {"status": "completed", "mode": "dry_run"}

        try:
            # Storyboard is already produced by creative_dir; just validate/record
            storyboard_path = Path("outputs/storyboards/final_storyboard.json")
            if not storyboard_path.exists():
                raise FileNotFoundError("final_storyboard.json not found")

            import json
            with open(storyboard_path, "r", encoding="utf-8") as f:
                sb = json.load(f)

            outputs = {"storyboard_json": str(storyboard_path)}
            self._stage_completed("storyboard", PipelineStatus.COMPLETED, outputs, None)
            return {"status": "completed", "outputs": outputs}
        except Exception as exc:
            self._stage_completed("storyboard", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}

    def run_video(self) -> dict[str, Any]:
        """Run the Video stage (OpenMontage adapter)."""
        self._stage_started("video")
        # If storyboard is blocked, video is blocked
        storyboard_result = self.stage_results.get("storyboard", {})
        if storyboard_result.get("status") != PipelineStatus.COMPLETED:
            self._stage_blocked(
                "video",
                f"storyboard stage not completed (status={storyboard_result.get('status')})",
            )
            return {"status": "blocked", "reason": "storyboard stage not completed"}

        if self.mode == "dry_run":
            self._stage_completed(
                "video",
                PipelineStatus.COMPLETED,
                {"note": "dry_run: video stage exercised via fixture"},
                {"mode": "dry_run"},
            )
            return {"status": "completed", "mode": "dry_run"}

        # Live mode: try OpenMontage
        try:
            result = run_video_agent(mode=self.mode)
            # Map the result to orchestrator expected format
            status = (
                PipelineStatus.COMPLETED
                if result["status"] == "completed"
                else PipelineStatus.FAILED
            )
            outputs = result.get("outputs", {})
            error = None
            if result["status"] != "completed":
                error = {"error": result.get("error", "Unknown error")}
            self._stage_completed("video", status, outputs, error)
            return {
                "status": result["status"],
                "outputs": outputs,
                "mode": result.get("mode", "live"),
            }
        except VideoAgentError as exc:
            self._stage_completed("video", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}
        except Exception as exc:
            self._stage_blocked(
                "video",
                f"Unexpected error: {exc}",
            )
            return {"status": "blocked", "error": str(exc)}

    def run_quality(self) -> dict[str, Any]:
        """Run the Quality Validation stage."""
        self._stage_started("quality")
        # If video is blocked, quality is blocked
        video_result = self.stage_results.get("video", {})
        if video_result.get("status") != PipelineStatus.COMPLETED:
            self._stage_blocked(
                "quality",
                f"video stage not completed (status={video_result.get('status')})",
            )
            return {"status": "blocked", "reason": "video stage not completed"}

        if self.mode == "dry_run":
            self._stage_completed(
                "quality",
                PipelineStatus.COMPLETED,
                {"note": "dry_run: quality exercised via fixtures"},
                {"mode": "dry_run"},
            )
            return {"status": "completed", "mode": "dry_run"}

        # Validate existing outputs using Quality Agent
        try:
            result = run_quality_agent(mode=self.mode)
            # Map the result to orchestrator expected format
            status = (
                PipelineStatus.COMPLETED
                if result["status"] in ("pass", "warning")
                else PipelineStatus.FAILED
            )
            outputs = result.get("outputs", {})
            error = None
            if result["status"] == "fail":
                error = {
                    "errors": result.get("errors", []),
                    "warnings": result.get("warnings", []),
                }
            elif result["status"] == "warning":
                error = {
                    "warnings": result.get("warnings", []),
                }
            self._stage_completed("quality", status, outputs, error)
            return {
                "status": result["status"],
                "outputs": outputs,
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
                "mode": result.get("mode", "live"),
            }
        except VideoAgentError as exc:
            self._stage_completed("quality", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}
        except Exception as exc:
            self._stage_completed("quality", PipelineStatus.FAILED, None, {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}

    # ------------------------------------------------------------------
    # Run the full pipeline
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Execute the complete pipeline in stage order."""
        # Reset manifest
        self.manifest = PipelineManifest(execution_mode=self.mode, started_at=datetime.now(timezone.utc).isoformat())
        self.stage_results = {}

        stages_map = {
            "ads": self.run_ads,
            "marketing": self.run_marketing,
            "research": self.run_research,
            "data": self.run_data,
            "script": self.run_script,
            "creative_dir": self.run_creative_dir,
            "storyboard": self.run_storyboard,
            "video": self.run_video,
            "quality": self.run_quality,
        }

        for stage_name in self.STAGE_ORDER:
            # Check if any dependency failed or was blocked
            deps = self.STAGE_DEPS.get(stage_name, [])
            deps_met = True
            for dep in deps:
                dep_status = self.stage_results.get(dep, {}).get("status")
                if dep_status in (PipelineStatus.FAILED, PipelineStatus.BLOCKED):
                    deps_met = False
                    self._stage_blocked(stage_name, f"upstream {dep} {dep_status}")
                    break

            if not deps_met:
                continue

            # Execute stage
            stage_fn = stages_map[stage_name]
            result = stage_fn()
            self.stage_results[stage_name] = result

            # Ensure manifest has an entry for this stage (mocked stages may
            # bypass _stage_started/_stage_completed, so we record here too)
            if not any(s.get("stage") == stage_name for s in self.manifest.stages):
                self.manifest.stages.append(
                    {
                        "stage": stage_name,
                        "status": result.get("status", "unknown"),
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "outputs": result.get("outputs"),
                        "error": result.get("error"),
                    }
                )

        # Persist manifest
        self._persist_manifest()

        return self.manifest.to_dict()

    # ------------------------------------------------------------------
    # Manifest persistence
    # ------------------------------------------------------------------

    def _persist_manifest(self) -> None:
        """Write outputs/run_manifest.json."""
        # Update overall status
        all_statuses = [s.get("status") for s in self.manifest.stages]
        if all(s == "completed" for s in all_statuses):
            self.manifest.overall_status = PipelineStatus.COMPLETED
        elif any(s == "failed" for s in all_statuses):
            self.manifest.overall_status = PipelineStatus.FAILED
        elif any(s == "blocked" for s in all_statuses):
            self.manifest.overall_status = PipelineStatus.BLOCKED
        else:
            self.manifest.overall_status = PipelineStatus.RUNNING
        self.manifest.completed_at = datetime.now(timezone.utc).isoformat()

        manifest_path = Path("outputs/run_manifest.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest.to_dict(), f, indent=2, ensure_ascii=False)

        # Refresh pipeline_status.json from the current manifest
        get_pipeline_status(manifest_path)


def main() -> None:
    """Entry point: python main.py."""
    from src.orchestrator import Orchestrator

    mode = os.environ.get("PIPELINE_MODE", "live")
    print(f"Pipeline mode: {mode}")
    print(f"PIPELINE_MODE environment variable: {mode}")

    orch = Orchestrator(mode=mode)
    result = orch.run()

    # Print summary
    print("\n=== Pipeline Summary ===")
    print(f"Execution mode: {result.get('execution_mode', 'live')}")
    print(f"Overall status: {result.get('overall_status', 'pending')}")
    print(f"Started at: {result.get('started_at')}")
    print(f"Completed at: {result.get('completed_at')}")

    if result.get("errors"):
        print(f"Errors/blockers: {json.dumps(result['errors'], indent=2)}")

    print("\nStage statuses:")
    for stage in result.get("stages", []):
        print(f"  {stage['stage']}: {stage['status']}")


if __name__ == "__main__":
    main()