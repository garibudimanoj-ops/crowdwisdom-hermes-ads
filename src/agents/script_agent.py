"""ScriptAgent - generate 3 video-ad concepts from research and insights."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.integrations.hermes_runner import HermesAgentRunner, HermesError
from src.models.ad_models import Scene, ScriptConcept


class ScriptAgentError(RuntimeError):
    """Raised when script agent operations fail."""


class ScriptAgent:
    """Generate three distinct video-ad concepts from research and insights."""

    DEFAULT_OUTPUT_DIR = Path("outputs/scripts")

    def __init__(
        self,
        hermes_runner: HermesAgentRunner | None = None,
        output_dir: Path | str | None = None,
    ) -> None:
        self.hermes_runner = hermes_runner
        self.output_dir = Path(output_dir or self.DEFAULT_OUTPUT_DIR)

    def _load_json(self, path: str) -> dict[str, Any]:
        """Load a JSON file."""
        p = Path(path)
        if not p.exists():
            raise ScriptAgentError(f"Not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _build_evidence_summary(self) -> str:
        """Build a compact evidence summary for the prompt."""
        insights = self._load_json("outputs/insights/marketing_insights.json")
        research = self._load_json("outputs/research/research.json")
        unique_data = self._load_json("data/processed/unique_data.json")
        ads_data = self._load_json("outputs/ads/ads.json")

        ads = ads_data.get("ads", [])
        ad = ads[0] if ads else {}
        ad_text = ad.get("ad_text", "")[:300]

        insights_data = insights.get("insights", {})
        hook_obs = insights_data.get("hooks", [{}])[0].get("observation", "")[:200] if insights_data.get("hooks") else ""
        pain_obs = insights_data.get("pain_points", [{}])[0].get("observation", "")[:200] if insights_data.get("pain_points") else ""
        icp_obs = insights_data.get("icps", [{}])[0].get("observation", "")[:200] if insights_data.get("icps") else ""
        promise_obs = insights_data.get("promises_offers", [{}])[0].get("observation", "")[:200] if insights_data.get("promises_offers") else ""
        cta_obs = insights_data.get("cta_patterns", [{}])[0].get("observation", "")[:200] if insights_data.get("cta_patterns") else ""

        findings = research.get("research_findings", [])
        top_findings = [f"{f.get('query_type')}: {f.get('query', '')[:100]}" for f in findings[:3]]

        unique_meta = unique_data.get("metadata", {})
        unique_status = unique_meta.get("status", "unknown")
        unique_data_available = unique_data.get("unique_data_available", True)
        concept_2_status = (
            "CONCEPT 2 IS BLOCKED: No CrowdWisdom unique data available."
            if not unique_data_available
            else "UNIQUE CROWDWISDOM DATA: AVAILABLE"
        )

        return (
            f"SOURCE AD: {ad.get('advertiser', 'Unknown')} - {ad.get('title', '')}\n"
            f"  Text: {ad_text}\n"
            f"  CTA: {ad.get('cta_text', 'N/A')}\n"
            f"  Platform: {ad.get('platform', 'Unknown')}\n\n"
            f"MARKETING INSIGHTS:\n"
            f"  Hook: {hook_obs}\n"
            f"  Pain: {pain_obs}\n"
            f"  ICP: {icp_obs}\n"
            f"  Promise: {promise_obs}\n"
            f"  CTA: {cta_obs}\n\n"
            f"RESEARCH FINDINGS:\n"
            f"  {top_findings[0]}\n"
            f"  {top_findings[1]}\n"
            f"  {top_findings[2]}\n\n"
            f"UNIQUE DATA STATUS: {concept_2_status}\n"
            f"Unique data metadata: {unique_meta}\n\n"
            "RULES FOR CONCEPT GENERATION:\n"
            "Do NOT invent CrowdWisdom statistics, testimonials, returns, or performance figures.\n"
            "Do NOT claim industry-wide patterns based on a single ad.\n"
            "If Concept 2 is BLOCKED, do not generate it — mark it unavailable.\n"
        )

    def _build_prompt(self, evidence_summary: str) -> str:
        """Build a concise script generation prompt for Hermes."""
        return f"""You are a senior creative director. Return ONLY a valid JSON array of exactly 3 concept objects.
No markdown, no code fences, no explanations, no extra text before or after JSON.

STRICT FORMATTING REQUIREMENTS:
- Every JSON string value must remain on ONE LINE (no literal newlines inside strings)
- Escape any internal newlines as \\n (backslash-n)
- Escape internal quotes as \\"
- Do NOT include surrounding prose or block descriptions

EXACT JSON SCHEMA - RETURN EXACTLY 3 OBJECTS IN THIS ORDER (concept_id 1, 2, 3):
[{{
  "concept_id": 1, "title": "The Trader's Signal Overload", "track": "pain_icp", 
  "target_icp": "Forex and crypto traders aged 25-45 following multiple signal channels", 
  "hook": "Trader staring at screen with contradictory buy/sell signals", 
  "story": "Trader overwhelmed by noise discovers CrowdWisdom structured clarity", 
  "duration_seconds": 45, "scenes": [{{"scene_id": "1", "timing": "0-5", 
  "visuals": "...", "narration": "...", "dialogue": "", "text": "", "sound": "", 
  "music": "", "transitions": "", "product_appearance": false, "cta": false}}], 
  "narration": "When every channel shouts a different direction, clarity is lost. CrowdWisdom brings the crowd to one voice, turning confusion into conviction", 
  "visual_direction": "Dark, cluttered desk with multiple monitors showing red/green arrows; shift to clean, blue-toned interface with single consensus line", 
  "sound_direction": "Start with overlapping urgent voice alerts, fade to calm ambient tone as clarity emerges", 
  "music_direction": "Tense, staccato electronic beats transitioning to steady, hopeful synth pad", 
  "minimal_text": "Signal clarity from the crowd", "cta": "See the consensus", 
  "evidence": ["ad insight: traders follow signal channels"], 
  "source_fact_claims": ["ad states traders follow signal channels"], 
  "creative_interpretation_claims": ["visualizing trader overwhelm and resolution via structured consensus; assuming CrowdWisdom provides confidence scores"], 
  "limitations": ["Based on single ad creative; does not eliminate trading risk; structured output quality depends on input signal validity"]
}}, {{
  "concept_id": 2, "title": "CrowdWisdom Signal Ledger", "track": "unique_data", 
  "target_icp": "Data-savvy traders requiring auditable sources", 
  "hook": "Close-up of dataset record with verification badge", 
  "story": "Camera pans across 79 immutable signal entries with provenance tags and integrity hashes", 
  "duration_seconds": 45, "scenes": [{{"scene_id": "1", "timing": "0-5", 
  "visuals": "...", "narration": "...", "dialogue": "", "text": "", "sound": "", 
  "music": "", "transitions": "", "product_appearance": false, "cta": false}}], 
  "narration": "Every signal in CrowdWisdom carries its source on its sleeve, so you know exactly where the wisdom comes from", 
  "visual_direction": "Clean data-table UI with alternating row colors, verification icons, and hash strings; subtle blockchain-style linking lines between records", 
  "sound_direction": "Soft keyboard taps for data entry, followed by a clear chime when a record passes verification", 
  "music_direction": "Minimalist plucky arpeggio with a steady pulse, underscoring reliability and precision", 
  "minimal_text": "Provenance in every signal", "cta": "Explore the ledger", 
  "evidence": ["79 records in 1 file; timestamped signal contributions with source tags"], 
  "source_fact_claims": ["Dataset contains 79 records; each record includes timestamp, trader identifier, signal direction, and source provenance field"], 
  "creative_interpretation_claims": ["Visualizing dataset as transparent ledger with integrity hashes and verification badges; assuming cryptographic linking and source-tagging mechanisms"], 
  "limitations": ["Dataset contents beyond count and file number are not disclosed; specific field names and validation logic are inferred, not confirmed"]
}}, {{
  "concept_id": 3, "title": "From Noise to Execution-Ready Signal", "track": "product_value", 
  "target_icp": "Active traders seeking actionable, low-latency trade ideas backed by crowd consensus", 
  "hook": "Split screen: left side chaotic signal feed, right side clean CrowdWisdom execution panel", 
  "story": "A trader toggles between raw signal noise and CrowdWisdom filtered consensus, watches the confidence metric rise as aligned traders increase, then clicks Execute to send a pre-validated order to their broker", 
  "duration_seconds": 45, "scenes": [{{"scene_id": "1", "timing": "0-5", 
  "visuals": "...", "narration": "...", "dialogue": "", "text": "", "sound": "", 
  "music": "", "transitions": "", "product_appearance": false, "cta": false}}], 
  "narration": "When the crowd agrees, the path forward is clear. CrowdWisdom turns consensus into execution-ready trades", 
  "visual_direction": "Left side saturated, jittery visual noise; right side cool-toned interface with gauge, consensus arrow, and one-click execution", 
  "sound_direction": "Left: dissonant electronic glitches; right: harmonic tone that rises with confidence, concluding with a soft confirmation click", 
  "music_direction": "Evolving motif: starts fragmented, resolves into a cohesive, uplifting melody as consensus builds", 
  "minimal_text": "Consensus that you can trade on", "cta": "Trade the consensus", 
  "evidence": ["Based on ad promise of accounts starting at $36 and ICP of traders seeking reliable signals; value proposition aligns with structured crowd intelligence and filtering"], 
  "source_fact_claims": ["Ad targets traders; ad offers accounts starting at $36; ad emphasizes stopping unqualified signal providers"], 
  "creative_interpretation_claims": ["Depicts CrowdWisdom providing filtered consensus, confidence metrics, and one-click execution; assumes integration with broker for order submission"], 
  "limitations": ["Execution flow and broker integration are conceptual; actual platform features and latency are not verified by provided evidence"]
}}]

REQUIREMENTS (ALL MANDATORY):
- Exactly 3 objects, concept_id 1/2/3, each with a DIFFERENT track: pain_icp, unique_data, product_value
- title is MANDATORY for every concept - do NOT omit it
- Each concept must include ALL of: concept_id, title, track, target_icp, hook, story, 
  scenes (array), narration, visual_direction, sound_direction, music_direction, 
  minimal_text, cta, duration_seconds, evidence, source_fact_claims, 
  creative_interpretation_claims, limitations
- scenes array must have 6-8 scenes with start_seconds/end_seconds timing
- duration_seconds must be 30-60 for each concept
- concept 2 MUST reference actual CrowdWisdom data records from data/processed/unique_data.json 
  and preserve provenance fields; do NOT invent metrics or performance figures
- concept 1 = pain/ICP: trader overwhelmed by conflicting signals → CrowdWisdom structured clarity
- concept 3 = product_value: how CrowdWisdom helps trader via structured crowd intelligence
- All strings must be single-line valid JSON. No newlines in any string value.

EVIDENCE:
{evidence_summary}
"""

    def _extract_json(self, response: str) -> Any:
        """Extract a valid JSON object from a Hermes response."""
        clean = response.strip()

        # Strip markdown code fences
        if clean.startswith("```"):
            lines = clean.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("{") or line.strip().startswith("["):
                    clean = "\n".join(lines[i:])
                    break
            clean = clean.rstrip("`").strip()
            if clean.endswith("```"):
                clean = clean[:-3].strip()

        # Extract first complete JSON array/object if surrounded by prose
        if not (clean.startswith("[") or clean.startswith("{")):
            bracket_start = clean.find("[")
            bracket_end = clean.rfind("]")
            if bracket_start >= 0 and bracket_end > bracket_start:
                clean = clean[bracket_start:bracket_end + 1]

        # Fix multi-line strings in JSON: escape literal newlines inside string values
        clean = self._fix_multiline_json_strings(clean)

        try:
            return json.loads(clean)
        except json.JSONDecodeError as exc:
            raise ScriptAgentError(f"Failed to parse Hermes JSON: {exc}") from exc

    def _fix_multiline_json_strings(self, json_str: str) -> str:
        """Fix multi-line strings in JSON by escaping literal newlines inside string values.

        Hermes LLM sometimes outputs JSON with unescaped newlines inside string values.
        This regex finds string values and escapes any literal newlines within them.
        """
        import re

        def _escape_newlines_in_string(match: re.Match) -> str:
            content = match.group(1)
            content = content.replace("\n", "\\n")
            return f'"{content}"'

        pattern = r'"((?:[^"\\]|\\.)*)"'
        result = re.sub(pattern, _escape_newlines_in_string, json_str, flags=re.DOTALL)
        return result

    def _parse_concepts(self, response: str) -> list[ScriptConcept]:
        """Parse Hermes response into ScriptConcept objects."""
        data = self._extract_json(response)

        if not isinstance(data, list) or len(data) != 3:
            raise ScriptAgentError(
                f"Expected 3 concepts, got {len(data) if isinstance(data, list) else 'non-list'}"
            )

        def normalize_scene(scene: dict[str, Any]) -> dict[str, Any]:
            """Normalize scene fields to match the existing Scene model."""
            sound = scene.get("sound", scene.get("sound_effects", []))
            if isinstance(sound, list):
                sound = "; ".join(str(s) for s in sound)
            music = scene.get("music", scene.get("music_direction", ""))
            if isinstance(music, list):
                music = "; ".join(str(m) for m in music)

            start = scene.get("start_seconds", 0)
            end = scene.get("end_seconds", start)
            timing = scene.get("timing", f"{start}-{end}")

            return {
                "scene_id": scene.get("scene_id", ""),
                "timing": timing,
                "visuals": scene.get("visual", scene.get("visuals", "")),
                "narration": scene.get("voiceover", scene.get("narration", "")),
                "dialogue": scene.get("dialogue"),
                "text": scene.get("on_screen_text", scene.get("text", "")),
                "sound": sound,
                "music": music,
                "transitions": scene.get("transition", scene.get("transitions", "")),
                "product_appearance": scene.get("product_appearance", False),
                "cta": scene.get("cta", False),
            }

        concepts = []
        for item in data:
            if not isinstance(item, dict):
                raise ScriptAgentError("Each concept must be an object")
            required = ["concept_id", "title", "track", "target_icp", "hook", "story",
                        "scenes", "narration", "duration_seconds", "cta"]
            for field in required:
                if field not in item:
                    raise ScriptAgentError(f"Missing field: {field}")

            scenes = [normalize_scene(s) for s in item["scenes"]]
            duration = item.get("duration_seconds", item.get("duration", 45))

            concept = ScriptConcept(
                concept_id=item["concept_id"],
                title=item["title"],
                target_icp=item["target_icp"],
                hook=item["hook"],
                story=item["story"],
                scenes=scenes,
                narration=item["narration"],
                visual_direction=item.get("visual_direction", ""),
                sound_direction=item.get("sound_direction", ""),
                music_direction=item.get("music_direction", ""),
                minimal_text=item.get("minimal_text", ""),
                cta=item["cta"],
                duration=duration,
                evidence=item.get("evidence", []),
            )
            concepts.append(concept)

        ids = sorted(c.concept_id for c in concepts)
        if ids != [1, 2, 3]:
            raise ScriptAgentError(f"Concept IDs must be 1,2,3; got {ids}")

        tracks = [next(i["track"] for i in data if i["concept_id"] == c.concept_id) for c in concepts]
        if set(tracks) != {"pain_icp", "unique_data", "product_value"}:
            raise ScriptAgentError(f"Invalid tracks: {tracks}")

        return concepts

    def _validate_concepts(self, concepts: list[ScriptConcept]) -> list[str]:
        """Validate concepts and return warnings."""
        warnings = []
        for c in concepts:
            dur = c.duration
            if dur < 30 or dur > 60:
                warnings.append(f"Concept {c.concept_id}: duration {dur}s outside 30-60s")
            if len(c.scenes) < 4:
                warnings.append(f"Concept {c.concept_id}: only {len(c.scenes)} scenes")
            total = 0
            for s in c.scenes:
                total += self._parse_timing_duration(s.timing)
            if total > 0 and abs(total - dur) > 5:
                warnings.append(f"Concept {c.concept_id}: scene sum {total}s vs duration {dur}s")
        return warnings

    def _parse_timing_duration(self, timing: str) -> int:
        """Parse 'start-end' timing string to duration in seconds."""
        import re

        if not timing:
            return 0

        match = re.match(r"^\s*(\d+)\s*-\s*(\d+)", timing)
        if not match:
            return 0

        try:
            start = int(match.group(1))
            end = int(match.group(2))
            return end - start
        except ValueError:
            return 0

    def run(self) -> dict[str, Any]:
        """Execute the script agent workflow with retry logic."""
        if self.hermes_runner is None:
            self.hermes_runner = HermesAgentRunner()

        evidence_summary = self._build_evidence_summary()
        prompt = self._build_prompt(evidence_summary)

        system_prompt = (
            "You are a senior creative director. Return ONLY a valid JSON array of exactly 3 concept objects. "
            "No markdown, no code fences, no explanations, no extra text before or after JSON. "
            "Every string value must be single-line (no literal newlines). Escape internal newlines as \\n."
        )

        # First attempt
        try:
            response = self.hermes_runner.run(prompt, system_prompt=system_prompt)
        except HermesError as exc:
            raise ScriptAgentError(f"Hermes generation failed: {exc}") from exc

        # Try to parse; retry once if malformed/truncated
        warnings: list[str] = []
        data = None
        try:
            data = self._extract_json(response)
        except ScriptAgentError:
            # Retry with stricter prompt
            retry_prompt = prompt + "\n\nIMPORTANT: Your previous output was incomplete or malformed. "
            retry_prompt += "Return ONLY the complete JSON array of 3 concepts. Keep all strings single-line and compact."
            retry_system = system_prompt + " Your output MUST be complete and parseable JSON."
            try:
                response = self.hermes_runner.run(retry_prompt, system_prompt=retry_system)
                data = self._extract_json(response)
                warnings.append("First attempt failed JSON parsing; retried and succeeded on second attempt.")
            except (ScriptAgentError, HermesError) as exc:
                raise ScriptAgentError(f"Hermes generation failed after retry: {exc}") from exc

        concepts = self._parse_concepts(response)
        warnings.extend(self._validate_concepts(concepts))

        self.output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = []
        for concept, raw in zip(concepts, data):
            output_path = self.output_dir / f"concept_{concept.concept_id}.json"
            payload = {
                "concept_id": concept.concept_id,
                "track": raw.get("track", ""),
                "concept": concept.model_dump(mode="json"),
            }
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            saved_files.append(str(output_path))

        result = {
            "generated_at": datetime.now().isoformat(),
            "concepts": [
                {"concept_id": c.concept_id, "title": c.title,
                 "duration": c.duration, "scenes": len(c.scenes)}
                for c in concepts
            ],
            "saved_files": saved_files,
            "warnings": warnings,
        }
        print(f"Script Agent completed: {len(concepts)} concepts generated.")
        for w in warnings:
            print(f"  WARNING: {w}")
        return result


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    agent = ScriptAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))
