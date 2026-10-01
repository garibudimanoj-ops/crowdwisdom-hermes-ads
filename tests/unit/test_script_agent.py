from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agents.script_agent import ScriptAgent, ScriptAgentError
from src.models.ad_models import Scene, ScriptConcept


class TestParseTimingDuration:
    def test_simple_range(self):
        agent = ScriptAgent()
        assert agent._parse_timing_duration("0-5") == 5
        assert agent._parse_timing_duration("5-10") == 5
        assert agent._parse_timing_duration("10-15") == 5

    def test_spaces(self):
        agent = ScriptAgent()
        assert agent._parse_timing_duration("0 - 5") == 5
        assert agent._parse_timing_duration("5 - 12") == 7

    def test_with_seconds_suffix(self):
        agent = ScriptAgent()
        assert agent._parse_timing_duration("0-5 seconds") == 5
        assert agent._parse_timing_duration("0-5 (5s)") == 5

    def test_empty_timing(self):
        agent = ScriptAgent()
        assert agent._parse_timing_duration("") == 0
        assert agent._parse_timing_duration(None) == 0

    def test_malformed_timing(self):
        agent = ScriptAgent()
        assert agent._parse_timing_duration("abc") == 0
        assert agent._parse_timing_duration("5") == 0
        assert agent._parse_timing_duration("a-b") == 0

    def test_single_digit(self):
        agent = ScriptAgent()
        assert agent._parse_timing_duration("0-45") == 45


class TestJSONExtraction:
    def test_valid_direct_json(self):
        agent = ScriptAgent()
        response = '[{"concept_id": 1, "title": "Test"}]'
        result = agent._extract_json(response)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_json_inside_code_fence(self):
        agent = ScriptAgent()
        response = "```json\n[{\"concept_id\": 1}]\n```"
        result = agent._extract_json(response)
        assert isinstance(result, list)

    def test_json_surrounded_by_prose(self):
        agent = ScriptAgent()
        response = "Here is the JSON: [{\"concept_id\": 1}] and more text."
        result = agent._extract_json(response)
        assert isinstance(result, list)

    def test_malformed_json_raises(self):
        agent = ScriptAgent()
        with pytest.raises(ScriptAgentError):
            agent._extract_json("not valid json {{{")

    def test_empty_response_raises(self):
        agent = ScriptAgent()
        with pytest.raises(ScriptAgentError):
            agent._extract_json("")


def _make_3_concepts(primary_concept: dict) -> str:
    """Helper to wrap a single concept into a valid 3-concept array."""
    c1 = dict(primary_concept)
    c1["concept_id"] = 1
    c1["track"] = "pain_icp"
    c2 = {
        "concept_id": 2, "title": "C2", "track": "unique_data",
        "target_icp": "t", "hook": "H", "story": "S",
        "duration_seconds": 45, "cta": "V",
        "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}],
        "narration": "N", "evidence": []
    }
    c3 = {
        "concept_id": 3, "title": "C3", "track": "product_value",
        "target_icp": "t", "hook": "H", "story": "S",
        "duration_seconds": 45, "cta": "V",
        "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}],
        "narration": "N", "evidence": []
    }
    return json.dumps([c1, c2, c3])


class TestSceneNormalization:
    def test_timing_mapping(self):
        agent = ScriptAgent()
        response = _make_3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 45, "cta": "Visit",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "V"}],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        scene = concepts[0].scenes[0]
        assert scene.timing == "0-5"
        assert scene.visuals == "X"
        assert scene.narration == "V"

    def test_voiceover_to_narration(self):
        agent = ScriptAgent()
        response = _make_3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 45, "cta": "Visit",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "My voice"}],
            "narration": "Full narration", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        assert concepts[0].scenes[0].narration == "My voice"

    def test_sound_list_to_string(self):
        agent = ScriptAgent()
        response = _make_3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 45, "cta": "Visit",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "sound_effects": ["s1", "s2"]}],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        assert concepts[0].scenes[0].sound == "s1; s2"


class TestValidation:
    def _3_concepts(self, primary: dict) -> str:
        c1 = dict(primary)
        c1["concept_id"] = 1
        c1["track"] = "pain_icp"
        c2 = {
            "concept_id": 2, "title": "C2", "track": "unique_data",
            "target_icp": "t", "hook": "H", "story": "S",
            "duration_seconds": 45, "cta": "V",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}],
            "narration": "N", "evidence": []
        }
        c3 = {
            "concept_id": 3, "title": "C3", "track": "product_value",
            "target_icp": "t", "hook": "H", "story": "S",
            "duration_seconds": 45, "cta": "V",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}],
            "narration": "N", "evidence": []
        }
        return json.dumps([c1, c2, c3])

    def test_valid_concept(self):
        agent = ScriptAgent()
        response = self._3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 45, "cta": "Visit",
            "scenes": [
                {"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "V"},
                {"scene_id": "2", "timing": "5-12", "visual": "Y", "voiceover": "V2"},
                {"scene_id": "3", "timing": "12-20", "visual": "Z", "voiceover": "V3"},
                {"scene_id": "4", "timing": "20-28", "visual": "W", "voiceover": "V4"},
                {"scene_id": "5", "timing": "28-35", "visual": "V", "voiceover": "V5"},
                {"scene_id": "6", "timing": "35-45", "visual": "U", "voiceover": "V6"},
            ],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        warnings = agent._validate_concepts(concepts)
        # Only concept 1 (primary) should have no warnings; 2 and 3 have 1 scene each from helper
        primary_warnings = [w for w in warnings if "Concept 1" in w]
        assert len(primary_warnings) == 0

    def test_below_30_seconds(self):
        agent = ScriptAgent()
        response = self._3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 20, "cta": "Visit",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "V"}],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        warnings = agent._validate_concepts(concepts)
        assert any("outside 30-60s" in w for w in warnings)

    def test_above_60_seconds(self):
        agent = ScriptAgent()
        response = self._3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 90, "cta": "Visit",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "V"}],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        warnings = agent._validate_concepts(concepts)
        assert any("outside 30-60s" in w for w in warnings)

    def test_fewer_than_4_scenes(self):
        agent = ScriptAgent()
        response = self._3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 45, "cta": "Visit",
            "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "V"}],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        warnings = agent._validate_concepts(concepts)
        assert any("only" in w and "scenes" in w for w in warnings)

    def test_scene_timing_mismatch(self):
        agent = ScriptAgent()
        response = self._3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 45, "cta": "Visit",
            "scenes": [
                {"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "V"},
                {"scene_id": "2", "timing": "5-10", "visual": "Y", "voiceover": "V2"},
            ],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        warnings = agent._validate_concepts(concepts)
        assert any("scene sum" in w for w in warnings)

    def test_malformed_timing(self):
        agent = ScriptAgent()
        response = self._3_concepts({
            "title": "Test", "target_icp": "traders", "hook": "Hook", "story": "Story",
            "duration_seconds": 45, "cta": "Visit",
            "scenes": [{"scene_id": "1", "timing": "invalid", "visual": "X", "voiceover": "V"}],
            "narration": "N", "evidence": []
        })
        concepts = agent._parse_concepts(response)
        warnings = agent._validate_concepts(concepts)
        total = sum(agent._parse_timing_duration(s.timing) for s in concepts[0].scenes)
        assert total == 0


class TestSerialization:
    def test_scene_model_dump_json_serializable(self):
        scene = Scene(
            scene_id="1", timing="0-5", visuals="Test", narration="Voice",
        )
        serialized = scene.model_dump(mode="json")
        json_str = json.dumps(serialized)
        assert isinstance(json_str, str)
        assert json.loads(json_str)["timing"] == "0-5"

    def test_script_concept_model_dump_json_serializable(self):
        concept = ScriptConcept(
            concept_id=1, title="Test", target_icp="traders",
            hook="Hook", story="Story", duration=45, narration="N",
            visual_direction="Cinematic", sound_direction="",
            music_direction="", minimal_text="", cta="Visit",
            scenes=[Scene(scene_id="1", timing="0-5", visuals="X", narration="V")],
            evidence=["source"],
        )
        serialized = concept.model_dump(mode="json")
        json_str = json.dumps(serialized)
        loaded = json.loads(json_str)
        assert loaded["concept_id"] == 1
        assert loaded["duration"] == 45


class TestCreativeRequirements:
    def test_exactly_3_concepts(self):
        agent = ScriptAgent()
        response = json.dumps([
            {"concept_id": 1, "title": "C1", "track": "pain_icp", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
            {"concept_id": 2, "title": "C2", "track": "unique_data", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
            {"concept_id": 3, "title": "C3", "track": "product_value", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
        ])
        concepts = agent._parse_concepts(response)
        assert len(concepts) == 3

    def test_distinct_tracks(self):
        agent = ScriptAgent()
        response = json.dumps([
            {"concept_id": 1, "title": "C1", "track": "pain_icp", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
            {"concept_id": 2, "title": "C2", "track": "unique_data", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
            {"concept_id": 3, "title": "C3", "track": "product_value", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
        ])
        concepts = agent._parse_concepts(response)
        tracks = [c.title for c in concepts]
        assert len(set(tracks)) == 3

    def test_missing_duplicate_tracks_raises(self):
        agent = ScriptAgent()
        response = json.dumps([
            {"concept_id": 1, "title": "C1", "track": "pain_icp", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
            {"concept_id": 2, "title": "C2", "track": "pain_icp", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
            {"concept_id": 3, "title": "C3", "track": "product_value", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
        ])
        with pytest.raises(ScriptAgentError):
            agent._parse_concepts(response)

    def test_concept_2_no_data_available(self):
        """Concept 2 must handle missing CrowdWisdom data honestly."""
        agent = ScriptAgent()
        response = json.dumps([
            {"concept_id": 1, "title": "C1", "track": "pain_icp", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
            {"concept_id": 2, "title": "C2", "track": "unique_data", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": [], "limitations": ["Unique CrowdWisdom data is not available"]},
            {"concept_id": 3, "title": "C3", "track": "product_value", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []},
        ])
        concepts = agent._parse_concepts(response)
        assert concepts[1].concept_id == 2


class TestParseConceptsValidation:
    def test_wrong_number_of_concepts_raises(self):
        agent = ScriptAgent()
        response = json.dumps([{"concept_id": 1, "title": "C1", "track": "pain_icp", "target_icp": "t", "hook": "H", "story": "S", "duration_seconds": 45, "cta": "V", "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}], "narration": "N", "evidence": []}])
        with pytest.raises(ScriptAgentError):
            agent._parse_concepts(response)

    def test_non_list_response_raises(self):
        agent = ScriptAgent()
        response = '{"concept_id": 1}'
        with pytest.raises(ScriptAgentError):
            agent._parse_concepts(response)


class TestSavePath:
    def test_model_dump_before_json_dump(self):
        """Verify that concept.model_dump(mode='json') is called before json.dump."""
        agent = ScriptAgent()
        concept = ScriptConcept(
            concept_id=1, title="Test", target_icp="traders",
            hook="Hook", story="Story", duration=45, narration="N",
            visual_direction="Cinematic", sound_direction="",
            music_direction="", minimal_text="", cta="Visit",
            scenes=[Scene(scene_id="1", timing="0-5", visuals="X", narration="V")],
            evidence=["source"],
        )
        serialized = concept.model_dump(mode="json")
        assert isinstance(serialized, dict)
        json_str = json.dumps(serialized)
        loaded = json.loads(json_str)
        assert loaded["concept_id"] == 1
        assert loaded["scenes"][0]["timing"] == "0-5"


class TestTitleRequirement:
    """Test that title field is explicitly required."""
    
    def test_prompt_mentions_title_requirement(self):
        """Verify the prompt explicitly mentions title as required."""
        agent = ScriptAgent()
        evidence = agent._build_evidence_summary()
        prompt = agent._build_prompt(evidence)
        
        # Check that title is explicitly mentioned as required
        assert '"title":' in prompt
        assert "title is MANDATORY" in prompt
        assert '"title": "The Trader\'s Signal Overload"' in prompt
        assert '"title": "CrowdWisdom Signal Ledger"' in prompt
        assert '"title": "From Noise to Execution-Ready Signal"' in prompt

    def test_missing_title_raises_error(self):
        """Verify that concepts missing title are rejected."""
        agent = ScriptAgent()
        # Create a response where the first concept is missing title
        response = json.dumps([
            {
                "concept_id": 1,
                "track": "pain_icp",
                "target_icp": "traders",
                "hook": "Hook",
                "story": "Story",
                "duration_seconds": 45,
                "cta": "Visit",
                "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "V"}],
                "narration": "N",
                "evidence": []
                # Missing title intentionally
            },
            {
                "concept_id": 2,
                "title": "C2",
                "track": "unique_data",
                "target_icp": "t",
                "hook": "H",
                "story": "S",
                "duration_seconds": 45,
                "cta": "V",
                "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}],
                "narration": "N",
                "evidence": []
            },
            {
                "concept_id": 3,
                "title": "C3",
                "track": "product_value",
                "target_icp": "t",
                "hook": "H",
                "story": "S",
                "duration_seconds": 45,
                "cta": "V",
                "scenes": [{"scene_id": "1", "timing": "0-5", "visual": "X", "voiceover": "VO"}],
                "narration": "N",
                "evidence": []
            }
        ])
        
        # Should raise ScriptAgentError with "Missing field: title"
        with pytest.raises(ScriptAgentError) as exc_info:
            agent._parse_concepts(response)
        
        assert "Missing field: title" in str(exc_info.value)
