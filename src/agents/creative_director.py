from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.integrations.hermes_runner import HermesAgentRunner, HermesError
from src.models.ad_models import Storyboard, Scene
from src.agents.script_agent import ScriptAgent, ScriptAgentError


class CreativeDirectorError(RuntimeError):
    """Raised when creative director operations fail."""


class CreativeDirector:
    """Review three script concepts and produce the final production storyboard."""

    DEFAULT_OUTPUT_DIR = Path("outputs/storyboards")
    DEFAULT_SCRIPTS_DIR = Path("outputs/scripts")

    SCORING_CRITERIA = [
        "visual_hook",
        "clarity",
        "emotional_progression",
        "product_relevance",
        "evidence_integrity",
        "cinematic_continuity",
        "sound_opportunities",
        "visual_novelty",
        "cta_integration",
    ]

    def __init__(
        self,
        hermes_runner: HermesAgentRunner | None = None,
        scripts_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
    ) -> None:
        self.hermes_runner = hermes_runner
        self.scripts_dir = Path(scripts_dir or self.DEFAULT_SCRIPTS_DIR)
        self.output_dir = Path(output_dir or self.DEFAULT_OUTPUT_DIR)

    def _load_concepts(self) -> list[dict[str, Any]]:
        """Load all three concept files."""
        concepts = []
        for i in range(1, 4):
            path = self.scripts_dir / f"concept_{i}.json"
            if not path.exists():
                raise CreativeDirectorError(f"Concept file not found: {path}")
            with path.open("r", encoding="utf-8") as f:
                concepts.append(json.load(f))
        return concepts

    def _get_blocked_concepts(self, concepts: list[dict[str, Any]]) -> list[int]:
        """Identify concept IDs that are blocked/unavailable."""
        blocked = []
        for c in concepts:
            concept_data = c.get("concept", {})
            limitations = concept_data.get("limitations", [])
            if any("not available" in lim.lower() or "blocked" in lim.lower() for lim in limitations):
                blocked.append(c.get("concept_id"))
        return blocked

    def _load_research_summary(self) -> str:
        """Load research for evidence integrity checks."""
        path = Path("outputs/research/research.json")
        if not path.exists():
            return "No research data found."
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("research_metadata", {})
        return (
            f"Research: {meta.get('total_queries', 0)} queries, "
            f"{meta.get('total_results', 0)} results, "
            f"single_ad_observation: {meta.get('single_ad_observation', False)}. "
            f"Limitation: {meta.get('limitation', 'N/A')}"
        )

    def _score_concepts(self, concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Score each concept across all criteria (deterministic scoring based on structure)."""
        scores = []
        for concept in concepts:
            track = concept.get("track", "")
            score_breakdown = {}
            total = 0

            for criterion in self.SCORING_CRITERIA:
                s = 0
                scenes = concept.get("scenes", [])
                narration = concept.get("narration", "")

                if criterion == "visual_hook":
                    hook = concept.get("hook", "")
                    if hook and len(hook) > 20:
                        s += 3
                    if any("close" in str(sc.get("visual", "")).lower() for sc in scenes):
                        s += 2

                elif criterion == "clarity":
                    story = concept.get("story", "")
                    if story and len(story) > 50:
                        s += 3
                    if len(scenes) >= 6:
                        s += 2

                elif criterion == "emotional_progression":
                    if len(scenes) >= 5:
                        actions = [str(sc.get("action", "")) for sc in scenes]
                        if any("chaos" in a.lower() or "noise" in a.lower() or "clutter" in a.lower() for a in actions):
                            s += 2
                        if any("clarity" in a.lower() or "order" in a.lower() or "structured" in a.lower() or "resolve" in a.lower() for a in actions):
                            s += 3
                    if s > 0:
                        s += 1

                elif criterion == "product_relevance":
                    cta = concept.get("cta", "")
                    if "crowdwisdom" in cta.lower():
                        s += 3
                    if concept.get("product_appearance_in_story", False) or "crowdwisdom" in str(concept.get("story", "")).lower():
                        s += 2

                elif criterion == "evidence_integrity":
                    evidence = concept.get("evidence", [])
                    source_facts = concept.get("source_fact_claims", [])
                    creative_interp = concept.get("creative_interpretation_claims", [])
                    if len(evidence) > 0:
                        s += 2
                    if len(source_facts) > 0:
                        s += 2
                    if len(creative_interp) > 0:
                        s += 1
                    if track == "unique_data" and concept.get("track_note", "").lower().find("not") >= 0 and concept.get("track_note", "").lower().find("data") >= 0:
                        s += 1

                elif criterion == "cinematic_continuity":
                    if all(sc.get("transition") for sc in scenes):
                        s += 2
                    if len(scenes) >= 6:
                        s += 2
                    if any(sc.get("camera") for sc in scenes):
                        s += 1

                elif criterion == "sound_opportunities":
                    if all(sc.get("sound_effects") is not None for sc in scenes):
                        s += 2
                    if concept.get("sound_direction"):
                        s += 1
                    if concept.get("music_direction"):
                        s += 1

                elif criterion == "visual_novelty":
                    if "eye" in concept.get("hook", "").lower() or "reflection" in concept.get("hook", "").lower():
                        s += 2
                    if len(scenes) >= 6:
                        s += 2
                    visuals = [str(sc.get("visual", "")).lower() for sc in scenes]
                    if len(set(v[:30] for v in visuals)) >= len(visuals) * 0.5:
                        s += 1

                elif criterion == "cta_integration":
                    cta = concept.get("cta", "")
                    if cta and "crowdwisdom" in cta.lower():
                        s += 3
                    last_scenes = scenes[-2:] if len(scenes) >= 2 else scenes
                    if any("cta" in str(sc).lower() or "call" in str(sc).lower() or "visit" in str(sc).lower() for sc in last_scenes):
                        s += 2

                score_breakdown[criterion] = s
                total += s

            max_possible = 10 * len(self.SCORING_CRITERIA)
            avg_score = total / max_possible if max_possible > 0 else 0
            scores.append({
                "concept_id": concept.get("concept_id"),
                "title": concept.get("title"),
                "track": track,
                "total": total,
                "max_possible": max_possible,
                "avg_score": round(avg_score, 2),
                "breakdown": score_breakdown,
            })

        scores.sort(key=lambda x: x["total"], reverse=True)
        return scores

    def _build_review_prompt(self, concepts: list[dict[str, Any]], scores: list[dict[str, Any]], research_summary: str) -> str:
        """Build the creative review prompt for Hermes."""
        scores_json = json.dumps(scores, indent=2)
        concepts_json = json.dumps(concepts, indent=2)
        blocked = self._get_blocked_concepts(concepts)
        blocked_note = (
            f"\nBLOCKED CONCEPTS (do NOT select these for the final storyboard): {blocked}\n"
            if blocked
            else ""
        )
        return (
            "You are a senior creative director reviewing three video-ad concepts for CrowdWisdomTrading.\n\n"
            "RESEARCH CONTEXT:\n"
            f"{research_summary}\n\n"
            "CONCEPTS (JSON):\n"
            f"{concepts_json}\n\n"
            "SCORING (already computed):\n"
            f"{scores_json}\n\n"
            "YOUR TASK:\n"
            "1. Do NOT simply pick the first concept.\n"
            "2. Review each concept for:\n"
            "   - visual hook strength\n"
            "   - narrative clarity and emotional arc\n"
            "   - cinematic potential (camera, lighting, transitions)\n"
            "   - sound and music opportunities\n"
            "   - evidence integrity (source_fact vs creative_interpretation)\n"
            "   - CTA integration\n"
            "   - WARNING: Track 2 (unique_data) MUST address no_data_available status\n"
            f"{blocked_note}"
            "3. Select the BEST concept as the basis for the final storyboard.\n"
            "4. Improve the chosen concept: strengthen first 3 seconds, add cinematic detail,\n"
            "   refine narration, ensure visual continuity, improve CTA integration.\n"
            "5. Produce the final storyboard with 7-9 scenes (45 seconds, 9:16).\n\n"
            "OUTPUT FORMAT - Return ONLY valid JSON:\n"
            "{\n"
            "  \"selected_concept_id\": 1,\n"
            "  \"selection_reason\": \"Selected because...\",\n"
            "  \"reviews\": [\n"
            "    {\n"
            "      \"concept_id\": 1,\n"
            "      \"strengths\": [\"...\", \"...\"],\n"
            "      \"weaknesses\": [\"...\", \"...\"],\n"
            "      \"improvement_notes\": \"...\"\n"
            "    },\n"
            "    ...\n"
            "  ],\n"
            "  \"final_storyboard\": {\n"
            "    \"campaign\": \"CrowdWisdomTrading\",\n"
            "    \"title\": \"The Noise\",\n"
            "    \"duration_seconds\": 45,\n"
            "    \"aspect_ratio\": \"9:16\",\n"
            "    \"hook\": {\"first_3_seconds\": \"...\", \"visual\": \"...\"},\n"
            "    \"scenes\": [\n"
            "      {\n"
            "        \"scene_id\": 1,\n"
            "        \"start_seconds\": 0,\n"
            "        \"end_seconds\": 5,\n"
            "        \"duration_seconds\": 5,\n"
            "        \"visual\": \"...\",\n"
            "        \"camera\": \"...\",\n"
            "        \"lighting\": \"...\",\n"
            "        \"environment\": \"...\",\n"
            "        \"subject\": \"...\",\n"
            "        \"action\": \"...\",\n"
            "        \"voiceover\": \"...\",\n"
            "        \"sound_effects\": [],\n"
            "        \"music_direction\": \"...\",\n"
            "        \"transition\": \"...\",\n"
            "        \"on_screen_text\": \"\",\n"
            "        \"asset_requirements\": [],\n"
            "        \"data_references\": []\n"
"      }\n"
             "    ],\n"
             "    \"cta\": {\"voiceover\": \"...\", \"visual\": \"...\"}\n"
             "  },\n"
             "  \"creative_review\": {\n"
             "    \"reviewed_at\": \"" + datetime.now().isoformat() + "\",\n"
             "    \"reviewer\": \"CreativeDirectorAgent\",\n"
             "    \"final_verdict\": \"...\"\n"
             "  }\n"
             "}\n\n"
             "IMPORTANT:\n"
             "- Final storyboard MUST have exactly 7-9 scenes\n"
             "- Scenes must sum to 30-60 seconds (target 45)\n"
             "- Distinguish source_fact claims from creative_interpretation\n"
             "- If selecting Track 2 (unique_data), explicitly mark data as not_yet_available\n"
             "- NEVER select a concept marked as blocked/unavailable\n"
             "- Return ONLY valid JSON, no markdown, no extra text"
        )

    def _parse_storyboard_response(self, response: str, concepts: list[dict[str, Any]]) -> dict[str, Any]:
        """Parse the creative director JSON response."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError as exc:
            raise CreativeDirectorError(f"Failed to parse Hermes JSON: {exc}") from exc

        required_keys = ["selected_concept_id", "reviews", "final_storyboard"]
        for key in required_keys:
            if key not in data:
                raise CreativeDirectorError(f"Missing required key in review response: {key}")

        # Validate that selected concept is not blocked
        selected_id = data.get("selected_concept_id")
        blocked_concepts = self._get_blocked_concepts(concepts)
        if selected_id in blocked_concepts:
            raise CreativeDirectorError(
                f"Selected concept {selected_id} is blocked/unavailable and cannot be chosen"
            )

        storyboard = data["final_storyboard"]
        scenes = storyboard.get("scenes", [])
        if len(scenes) < 7 or len(scenes) > 9:
            raise CreativeDirectorError(f"Final storyboard must have 7-9 scenes, got {len(scenes)}")

        total = sum(sc.get("duration_seconds", 0) for sc in scenes)
        if total < 30 or total > 60:
            raise CreativeDirectorError(f"Final storyboard duration {total}s outside 30-60s range")

        duration = storyboard.get("duration_seconds", 0)
        if duration < 30 or duration > 60:
            raise CreativeDirectorError(f"Storyboard duration {duration}s outside 30-60s range")

        if storyboard.get("aspect_ratio") != "9:16":
            raise CreativeDirectorError(f"Storyboard aspect ratio must be 9:16, got {storyboard.get('aspect_ratio')}")

        return data

    def _save_artifacts(self, result: dict[str, Any]) -> list[str]:
        """Save storyboard and review artifacts."""
        saved = []

        self.output_dir.mkdir(parents=True, exist_ok=True)

        storyboard = result["final_storyboard"]
        storyboard_path = self.output_dir / "final_storyboard.json"
        with storyboard_path.open("w", encoding="utf-8") as f:
            json.dump(storyboard, f, indent=2, ensure_ascii=False)
        saved.append(str(storyboard_path))

        review_path = Path("outputs/creative_review.json")
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review = result.get("creative_review", {})
        review_data = {
            "selected_concept_id": result["selected_concept_id"],
            "selection_reason": result["selection_reason"],
            "reviews": result["reviews"],
            "review_artifact": review,
        }
        with review_path.open("w", encoding="utf-8") as f:
            json.dump(review_data, f, indent=2, ensure_ascii=False)
        saved.append(str(review_path))

        return saved

    def run(self, concepts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Execute the creative director workflow."""
        if concepts is None:
            print("Loading concepts...")
            concepts = self._load_concepts()

        print("Loading research summary...")
        research_summary = self._load_research_summary()

        print("Scoring concepts...")
        scores = self._score_concepts(concepts)
        print(json.dumps(scores, indent=2))

        prompt = self._build_review_prompt(concepts, scores, research_summary)

        system_prompt = (
            "You are a senior creative director. Return ONLY valid JSON matching the output format. "
            "No markdown, no explanations, no extra text."
        )

        if self.hermes_runner is None:
            self.hermes_runner = HermesAgentRunner()

        try:
            response = self.hermes_runner.run(prompt, system_prompt=system_prompt)
        except HermesError as exc:
            raise CreativeDirectorError(f"Hermes review failed: {exc}") from exc
        except Exception as exc:
            raise CreativeDirectorError(f"Hermes review failed: {exc}") from exc

        result = self._parse_storyboard_response(response, concepts)
        saved_files = self._save_artifacts(result)

        summary = {
            "generated_at": datetime.now().isoformat(),
            "selected_concept_id": result["selected_concept_id"],
            "title": result["final_storyboard"]["title"],
            "duration_seconds": result["final_storyboard"]["duration_seconds"],
            "scenes_count": len(result["final_storyboard"]["scenes"]),
            "saved_files": saved_files,
        }

        print(f"Creative Director completed. Selected concept {result['selected_concept_id']}.")
        return summary


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    director = CreativeDirector()
    result = director.run()
    print(json.dumps(result, indent=2))
