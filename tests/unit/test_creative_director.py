"""Tests for Creative Director blocked-concept handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.agents.creative_director import CreativeDirector, CreativeDirectorError
from src.models.ad_models import Scene


def _make_scene(
    scene_id: str = "1",
    duration_seconds: int = 5,
    visual: str = "X",
    narration: str = "N",
) -> dict[str, Any]:
    return {
        "scene_id": scene_id,
        "timing": f"0-{duration_seconds}",
        "duration_seconds": duration_seconds,
        "visual": visual,
        "voiceover": narration,
        "camera": "static",
        "lighting": "natural",
        "environment": "studio",
        "subject": "person",
        "action": "speaking",
        "sound_effects": [],
        "music_direction": "soft",
        "transition": "cut",
        "on_screen_text": "",
        "asset_requirements": [],
        "data_references": [],
    }


def _valid_storyboard_response(
    selected_concept_id: int = 1,
) -> str:
    scenes = [_make_scene(str(i), 5, f"Visual {i}", f"Narration {i}") for i in range(1, 8)]
    return json.dumps(
        {
            "selected_concept_id": selected_concept_id,
            "selection_reason": "Best concept",
            "reviews": [
                {
                    "concept_id": 1,
                    "strengths": ["hook"],
                    "weaknesses": [],
                    "improvement_notes": "",
                },
                {
                    "concept_id": 2,
                    "strengths": [],
                    "weaknesses": ["no data"],
                    "improvement_notes": "",
                },
                {
                    "concept_id": 3,
                    "strengths": ["value"],
                    "weaknesses": [],
                    "improvement_notes": "",
                },
            ],
            "final_storyboard": {
                "campaign": "CrowdWisdomTrading",
                "title": "The Noise",
                "duration_seconds": 35,
                "aspect_ratio": "9:16",
                "hook": {"first_3_seconds": "Hook", "visual": "Visual"},
                "scenes": scenes,
                "cta": {"voiceover": "Visit crowdwisdomtrading.com", "visual": "Logo"},
            },
            "creative_review": {
                "reviewed_at": "2026-01-01T00:00:00",
                "reviewer": "CreativeDirectorAgent",
                "final_verdict": "approved",
            },
        }
    )


class TestBlockedConceptDetection:
    def test_concept_2_with_nested_limitation_is_blocked(self) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {
                "concept_id": 2,
                "track": "unique_data",
                "concept": {"limitations": ["Unique CrowdWisdom data is not available"]},
            },
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        blocked = director._get_blocked_concepts(concepts)
        assert blocked == [2]

    def test_concept_2_with_multiple_limitations_is_blocked(self) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {
                "concept_id": 2,
                "track": "unique_data",
                "concept": {
                    "limitations": [
                        "Unique CrowdWisdom data is not available",
                        "No proprietary data",
                    ]
                },
            },
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        blocked = director._get_blocked_concepts(concepts)
        assert 2 in blocked

    def test_no_blocked_concepts_when_data_available(self) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {"concept_id": 2, "track": "unique_data", "concept": {}},
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        blocked = director._get_blocked_concepts(concepts)
        assert blocked == []

    def test_malformed_missing_concept_key_safely_handled(self) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp"},
            {"concept_id": 2, "track": "unique_data"},
            {"concept_id": 3, "track": "product_value"},
        ]
        blocked = director._get_blocked_concepts(concepts)
        assert blocked == []

    def test_malformed_missing_limitations_safely_handled(self) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {"concept_id": 2, "track": "unique_data", "concept": {"foo": "bar"}},
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        blocked = director._get_blocked_concepts(concepts)
        assert blocked == []


class TestBlockedConceptRejection:
    @patch("src.agents.creative_director.HermesAgentRunner")
    def test_parse_rejects_blocked_concept_2(self, mock_runner: MagicMock) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {
                "concept_id": 2,
                "track": "unique_data",
                "concept": {"limitations": ["Unique CrowdWisdom data is not available"]},
            },
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        mock_runner.return_value.run.return_value = _valid_storyboard_response(
            selected_concept_id=2
        )
        with patch.object(director, "hermes_runner", mock_runner().run):
            with pytest.raises(CreativeDirectorError, match="blocked/unavailable"):
                director._parse_storyboard_response(
                    _valid_storyboard_response(selected_concept_id=2), concepts
                )

    @patch("src.agents.creative_director.HermesAgentRunner")
    def test_parse_accepts_concept_1_when_2_is_blocked(
        self, mock_runner: MagicMock
    ) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {
                "concept_id": 2,
                "track": "unique_data",
                "concept": {"limitations": ["Unique CrowdWisdom data is not available"]},
            },
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        mock_runner.return_value.run.return_value = _valid_storyboard_response(
            selected_concept_id=1
        )
        result = director._parse_storyboard_response(
            _valid_storyboard_response(selected_concept_id=1), concepts
        )
        assert result["selected_concept_id"] == 1

    @patch("src.agents.creative_director.HermesAgentRunner")
    def test_parse_accepts_concept_3_when_2_is_blocked(
        self, mock_runner: MagicMock
    ) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {
                "concept_id": 2,
                "track": "unique_data",
                "concept": {"limitations": ["Unique CrowdWisdom data is not available"]},
            },
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        result = director._parse_storyboard_response(
            _valid_storyboard_response(selected_concept_id=3), concepts
        )
        assert result["selected_concept_id"] == 3

    def test_parse_accepts_concept_2_when_not_blocked(self) -> None:
        director = CreativeDirector()
        concepts = [
            {"concept_id": 1, "track": "pain_icp", "concept": {}},
            {"concept_id": 2, "track": "unique_data", "concept": {}},
            {"concept_id": 3, "track": "product_value", "concept": {}},
        ]
        result = director._parse_storyboard_response(
            _valid_storyboard_response(selected_concept_id=2), concepts
        )
        assert result["selected_concept_id"] == 2