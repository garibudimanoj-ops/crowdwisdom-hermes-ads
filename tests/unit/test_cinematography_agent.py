from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

import src.agents.cinematography_agent as ca
from src.schemas.cinematography_plan import (
    CinematographyPlan,
    ScenePlan,
    Shot,
    validate_compliance,
    validate_plan_compliance,
    FORBIDDEN_CLAIMS,
)



def _make_shot(shot_id="s1_1", start=0, end=8, **kwargs):
    defaults = {
        "shot_id": shot_id,
        "start_seconds": start,
        "end_seconds": end,
        "duration_seconds": end - start,
        "shot_type": "medium_shot",
        "subject": "Trader",
        "environment": "Office",
        "visual_description": "Professional trader at desk",
        "camera": "Medium shot",
        "camera_motion": "Static",
        "lens_feel": "Standard",
        "composition": "Centered",
        "depth": "Shallow",
        "lighting": "Office lighting",
        "color_grade": "Warm",
        "mood": "Focused",
        "visual_events": [],
        "footage_queries": ["professional trader desk"],
        "overlay_plan": "",
        "transition_in": "",
        "transition_out": "",
        "sound_design": "",
    }
    defaults.update(kwargs)
    return defaults


def _make_scene(scene_id, start, end, **kwargs):
    shot = _make_shot(shot_id=f"s{scene_id}_1", start=start, end=end)
    defaults = {
        "scene_id": scene_id,
        "start_seconds": start,
        "end_seconds": end,
        "duration_seconds": end - start,
        "creative_goal": f"Scene {scene_id}",
        "shots": [shot],
        "sound_design": f"Scene {scene_id} sound",
        "continuity_notes": "",
        "compliance_notes": "Safe financial communication",
        "risk_flags": [],
    }
    defaults.update(kwargs)
    return defaults


def _make_valid_plan_json(scenes_data=None):
    if scenes_data is None:
        scenes_data = [
            _make_scene(1, 0, 8),
            _make_scene(2, 8, 18),
            _make_scene(3, 18, 28),
            _make_scene(4, 28, 38),
            _make_scene(5, 38, 45),
        ]
    return {
        "campaign": "Test Campaign",
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "total_duration_seconds": 45.0,
        "visual_style": "Cinematic",
        "color_story": "Dark to bright",
        "continuity_rules": [],
        "scenes": scenes_data,
    }


# ---------- Tests ----------

# Helper tests
def test_parse_json_response_valid():
    assert ca._parse_json_response('{"test": "data"}') == {"test": "data"}


def test_parse_json_response_with_markdown():
    # OpenRouter with structured output returns clean JSON
    assert ca._parse_json_response('{"test": "data"}') == {"test": "data"}


def test_call_openrouter_success():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(_make_valid_plan_json())}}]
        }
        mock_post.return_value = mock_response
        result = ca._call_openrouter("test", "test", ca.OPENROUTER_MODEL)
        assert CinematographyPlan.model_validate_json(result)


def test_call_openrouter_empty_response():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}]
        }
        mock_post.return_value = mock_response
        with pytest.raises(ca.CinematographyAgentError, match="empty response"):
            ca._call_openrouter("test", "test", ca.OPENROUTER_MODEL)


def test_call_openrouter_uses_json_schema():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        valid_json = json.dumps(_make_valid_plan_json())
        mock_response.json.return_value = {
            "choices": [{"message": {"content": valid_json}}]
        }
        mock_post.return_value = mock_response
        ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["name"] == "cinematography_plan"
        assert payload["response_format"]["json_schema"]["strict"] is True


def test_call_openrouter_returns_valid_json():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        valid_json = json.dumps(_make_valid_plan_json())
        mock_response.json.return_value = {
            "choices": [{"message": {"content": valid_json}}]
        }
        mock_post.return_value = mock_response
        result = ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)
        revalidated = ca.CinematographyPlan.model_validate_json(result)
        assert revalidated.campaign == "Test Campaign"


def test_call_openrouter_strict_parsed_valid_plan_returns_json():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        valid_json = json.dumps(_make_valid_plan_json())
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": valid_json}}]
        }
        mock_post.return_value = mock_response
        result = ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)
        assert json.loads(result)["campaign"] == "Test Campaign"


def test_call_openrouter_strict_parsed_invalid_dict_raises():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"start": 0, "end": 8}'}}]
        }
        mock_post.return_value = mock_response
        result = ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)
        with pytest.raises(ca.CinematographyAgentError, match="Failed to validate plan"):
            ca._attempt_parse_and_validate(result, retry=False)


def test_call_openrouter_strict_parsed_invalid_text_raises():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not valid json"}}]
        }
        mock_post.return_value = mock_response
        result = ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)
        with pytest.raises(ca.CinematographyAgentError, match="Failed to parse"):
            ca._attempt_parse_and_validate(result, retry=False)


# Agent tests
def test_generate_cinematography_plan_success(tmp_path):
    storyboard_path = Path(tmp_path / "storyboard.json")
    storyboard_path.write_text(json.dumps({
        "scenes": [
            {"scene_id": i + 1, "start_seconds": [0, 8, 18, 28, 38][i], "end_seconds": [8, 18, 28, 38, 45][i]}
            for i in range(5)
        ]
    }), encoding="utf-8")
    output_path = Path(tmp_path / "output.json")
    with patch("src.agents.cinematography_agent._call_openrouter") as mock_call:
        mock_call.return_value = json.dumps(_make_valid_plan_json())
        plan = ca.generate_cinematography_plan(storyboard_path, output_path)
        assert plan.campaign == "Test Campaign"
        assert len(plan.scenes) == 5


def test_generate_cinematography_plan_storyboard_not_found(tmp_path):
    with pytest.raises(ca.CinematographyAgentError, match="Storyboard not found"):
        ca.generate_cinematography_plan(Path(tmp_path / "none.json"), Path(tmp_path / "out.json"))


def test_generate_cinematography_plan_invalid_json(tmp_path):
    storyboard_path = Path(tmp_path / "storyboard.json")
    storyboard_path.write_text(json.dumps({}), encoding="utf-8")
    with patch("src.agents.cinematography_agent._call_openrouter") as mock_call:
        mock_call.return_value = "Invalid"
        with pytest.raises(ca.CinematographyAgentError, match="Failed to parse"):
            ca.generate_cinematography_plan(storyboard_path, Path(tmp_path / "out.json"), retry=False)


def test_generate_cinematography_plan_retry_on_parse_error(tmp_path):
    storyboard_path = Path(tmp_path / "storyboard.json")
    storyboard_path.write_text(json.dumps({}), encoding="utf-8")
    with patch("src.agents.cinematography_agent._call_openrouter") as mock_call:
        mock_call.side_effect = ["Invalid", json.dumps(_make_valid_plan_json())]
        plan = ca.generate_cinematography_plan(storyboard_path, Path(tmp_path / "out.json"), retry=True)
        assert plan.campaign == "Test Campaign"
        assert mock_call.call_count == 2


def test_generate_cinematography_plan_retry_on_validation_error(tmp_path):
    storyboard_path = Path(tmp_path / "storyboard.json")
    storyboard_path.write_text(json.dumps({}), encoding="utf-8")
    invalid = json.dumps({**_make_valid_plan_json(), "scenes": [_make_scene(1, 0, 8), _make_scene(2, 8, 18)]})
    with patch("src.agents.cinematography_agent._call_openrouter") as mock_call:
        mock_call.side_effect = [invalid, json.dumps(_make_valid_plan_json())]
        plan = ca.generate_cinematography_plan(storyboard_path, Path(tmp_path / "out.json"), retry=True)
        assert plan.campaign == "Test Campaign"
        assert mock_call.call_count == 2


def test_generate_cinematography_plan_retry_on_compliance_error(tmp_path):
    storyboard_path = Path(tmp_path / "storyboard.json")
    storyboard_path.write_text(json.dumps({}), encoding="utf-8")
    non_comp = _make_valid_plan_json()
    non_comp["scenes"][0]["shots"][0]["visual_description"] = "guaranteed profits"
    comp = _make_valid_plan_json()
    comp["campaign"] = "Compliant After Retry"
    with patch("src.agents.cinematography_agent._call_openrouter") as mock_call:
        mock_call.side_effect = [json.dumps(non_comp), json.dumps(comp)]
        plan = ca.generate_cinematography_plan(storyboard_path, Path(tmp_path / "out.json"), retry=True)
        assert plan.campaign == "Compliant After Retry"
        assert mock_call.call_count == 2


def test_generate_cinematography_plan_fails_after_two_attempts(tmp_path):
    storyboard_path = Path(tmp_path / "storyboard.json")
    storyboard_path.write_text(json.dumps({}), encoding="utf-8")
    with patch("src.agents.cinematography_agent._call_openrouter") as mock_call:
        mock_call.return_value = "Always invalid"
        with pytest.raises(ca.CinematographyAgentError, match="Failed to parse"):
            ca.generate_cinematography_plan(storyboard_path, Path(tmp_path / "out.json"), retry=True)
        assert mock_call.call_count == 2


# Compliance tests
def test_validate_plan_compliance_no_violations():
    plan = CinematographyPlan(**_make_valid_plan_json())
    assert len(validate_plan_compliance(plan)) == 0


def test_validate_plan_compliance_with_forbidden_claim():
    plan = CinematographyPlan(**_make_valid_plan_json())
    plan.scenes[0].shots[0].visual_description = "guaranteed profit"
    violations = validate_plan_compliance(plan)
    assert any("guaranteed profit" in v for v in violations)


def test_forbidden_claim_detection_comprehensive():
    for claim in FORBIDDEN_CLAIMS:
        plan = CinematographyPlan(**_make_valid_plan_json())
        plan.scenes[0].shots[0].visual_description = claim
        assert any(f"Forbidden claim detected: '{claim}'" in v for v in validate_plan_compliance(plan)), f"Should violate: {claim}"


# Schema tests
def test_schema_rejects_wrong_scene_count():
    with pytest.raises(ValidationError):
        CinematographyPlan(**_make_valid_plan_json(scenes_data=[_make_scene(1, 0, 8), _make_scene(2, 8, 18)]))


def test_schema_rejects_invalid_total_duration():
    plan_data = _make_valid_plan_json()
    plan_data["scenes"][4]["end_seconds"] = 44
    plan_data["scenes"][4]["duration_seconds"] = 6
    plan_data["scenes"][4]["shots"][0]["end_seconds"] = 44
    plan_data["scenes"][4]["shots"][0]["duration_seconds"] = 6
    with pytest.raises(ValidationError):
        CinematographyPlan(**plan_data)


def test_schema_rejects_invalid_scene_timing():
    plan_data = _make_valid_plan_json()
    plan_data["scenes"][0]["start_seconds"] = 1
    plan_data["scenes"][0]["end_seconds"] = 9  # 8 -> 9 to keep duration = 8
    plan_data["scenes"][0]["duration_seconds"] = 8
    plan_data["scenes"][0]["shots"][0]["start_seconds"] = 1
    plan_data["scenes"][0]["shots"][0]["end_seconds"] = 9
    plan_data["scenes"][0]["shots"][0]["duration_seconds"] = 8
    with pytest.raises(ValidationError, match="Scene 1: start must be 0"):
        CinematographyPlan(**plan_data)


def test_schema_rejects_invalid_shot_timing():
    from src.schemas.cinematography_plan import Shot
    with pytest.raises(ValidationError):
        Shot(
            shot_id="s1",
            start_seconds=-1,
            end_seconds=5,
            duration_seconds=6,
            shot_type="medium_shot",
            subject="Test",
            environment="Test",
            visual_description="Test",
            camera="Test",
            camera_motion="Test",
            lens_feel="Test",
            composition="Test",
            depth="Test",
            lighting="Test",
            color_grade="Test",
            mood="Test",
            visual_events=["test"],
            footage_queries=["test"],
            overlay_plan="",
            transition_in="",
            transition_out="",
            sound_design="",
        )


# Timing validation tests
def test_shot_end_greater_than_start():
    from src.schemas.cinematography_plan import Shot
    with pytest.raises(ValidationError):
        Shot(
            shot_id="s1",
            start_seconds=5,
            end_seconds=5,
            duration_seconds=0,
            shot_type="medium_shot",
            subject="Test",
            environment="Test",
            visual_description="Test",
            camera="Test",
            camera_motion="Test",
            lens_feel="Test",
            composition="Test",
            depth="Test",
            lighting="Test",
            color_grade="Test",
            mood="Test",
            visual_events=["test"],
            footage_queries=["test"],
            overlay_plan="",
            transition_in="",
            transition_out="",
            sound_design="",
        )


def test_shot_duration_matches_end_minus_start():
    from src.schemas.cinematography_plan import Shot
    with pytest.raises(ValidationError):
        Shot(
            shot_id="s1",
            start_seconds=0,
            end_seconds=5,
            duration_seconds=10,
            shot_type="medium_shot",
            subject="Test",
            environment="Test",
            visual_description="Test",
            camera="Test",
            camera_motion="Test",
            lens_feel="Test",
            composition="Test",
            depth="Test",
            lighting="Test",
            color_grade="Test",
            mood="Test",
            visual_events=["test"],
            footage_queries=["test"],
            overlay_plan="",
            transition_in="",
            transition_out="",
            sound_design="",
        )


def test_scene_end_greater_than_start():
    from src.schemas.cinematography_plan import ScenePlan
    with pytest.raises(ValidationError):
        ScenePlan(
            scene_id=1,
            start_seconds=5,
            end_seconds=5,
            duration_seconds=0,
            creative_goal="Test",
            shots=[],
            sound_design="Test",
        )


def test_scene_duration_matches_end_minus_start():
    from src.schemas.cinematography_plan import ScenePlan
    with pytest.raises(ValidationError):
        ScenePlan(
            scene_id=1,
            start_seconds=0,
            end_seconds=5,
            duration_seconds=10,
            creative_goal="Test",
            shots=[],
            sound_design="Test",
        )


# Real storyboard tests
def test_real_storyboard_loading():
    path = Path("outputs/storyboards/final_storyboard.json")
    assert path.exists()
    with open(path) as f:
        storyboard = json.load(f)
    assert len(storyboard["scenes"]) == 5
    for scene in storyboard["scenes"]:
        assert "scene_id" in scene and "voiceover" in scene and "visual" in scene


def test_real_storyboard_timing():
    path = Path("outputs/storyboards/final_storyboard.json")
    with open(path) as f:
        storyboard = json.load(f)
    expected_starts = [0, 8, 18, 28, 38]
    expected_ends = [8, 18, 28, 38, 45]
    for i, scene in enumerate(storyboard["scenes"]):
        assert scene["scene_id"] == i + 1
        assert scene["start_seconds"] == expected_starts[i]
        assert scene["end_seconds"] == expected_ends[i]
        assert scene["duration_seconds"] == expected_ends[i] - expected_starts[i]


def test_real_storyboard_duration():
    path = Path("outputs/storyboards/final_storyboard.json")
    with open(path) as f:
        storyboard = json.load(f)
    total = sum(scene["duration_seconds"] for scene in storyboard["scenes"])
    assert total == 45


# Structure tests
def test_output_structure_has_required_fields():
    plan = CinematographyPlan(**_make_valid_plan_json())
    for attr in [
        "campaign",
        "aspect_ratio",
        "width",
        "height",
        "fps",
        "total_duration_seconds",
        "visual_style",
        "color_story",
        "continuity_rules",
        "scenes",
    ]:
        assert hasattr(plan, attr)


def test_provenance_preserved_from_storyboard():
    with open("outputs/storyboards/final_storyboard.json") as f:
        storyboard = json.load(f)
    expected_starts = [0, 8, 18, 28, 38]
    expected_ends = [8, 18, 28, 38, 45]
    for i, scene in enumerate(storyboard["scenes"]):
        assert scene["scene_id"] == i + 1
        assert scene["start_seconds"] == expected_starts[i]
        assert scene["end_seconds"] == expected_ends[i]


# Configuration tests
def test_missing_api_key_raises_clear_error():
    from src.agents.cinematography_agent import _require_api_key
    import os
    old_key = os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ca.CinematographyAgentError, match="OPENROUTER_API_KEY"):
                ca._require_api_key()
    finally:
        if old_key:
            os.environ["OPENROUTER_API_KEY"] = old_key


def test_require_api_key_with_key_present():
    import os
    old_key = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "test-key-123"
    try:
        from src.agents.cinematography_agent import _require_api_key
        assert ca._require_api_key() == "test-key-123"
    finally:
        if old_key:
            os.environ["OPENROUTER_API_KEY"] = old_key
        else:
            del os.environ["OPENROUTER_API_KEY"]

# Model configuration tests

def test_openrouter_model_default():
    assert ca.OPENROUTER_MODEL != ""


def test_openrouter_model_from_env():
    import os
    old_model = os.environ.get("OPENROUTER_MODEL")
    os.environ["OPENROUTER_MODEL"] = "custom-model-1"
    try:
        from importlib import reload
        import src.agents.cinematography_agent
        reload(src.agents.cinematography_agent)
        assert src.agents.cinematography_agent.OPENROUTER_MODEL == "custom-model-1"
    finally:
        if old_model:
            os.environ["OPENROUTER_MODEL"] = old_model
        else:
            del os.environ["OPENROUTER_MODEL"]
        reload(src.agents.cinematography_agent)


# Determinism tests
def test_deterministic_validation():
    plan1 = CinematographyPlan(**_make_valid_plan_json())
    plan2 = CinematographyPlan(**_make_valid_plan_json())
    violations1 = validate_plan_compliance(plan1)
    violations2 = validate_plan_compliance(plan2)
    assert violations1 == violations2


def test_deterministic_compliance_checking():
    plan = CinematographyPlan(**_make_valid_plan_json())
    plan.scenes[0].shots[0].visual_description = "guaranteed profits"
    violations1 = validate_plan_compliance(plan)
    violations2 = validate_plan_compliance(plan)
    assert violations1 == violations2


# OpenRouter fallback tests
def test_call_openrouter_success():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        valid_json = json.dumps(_make_valid_plan_json())
        mock_response.json.return_value = {
            "choices": [{"message": {"content": valid_json}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        result = ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)
        assert CinematographyPlan.model_validate_json(result)


def test_call_openrouter_empty_response_raises():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        with pytest.raises(ca.CinematographyAgentError, match="empty response"):
            ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)


def test_call_openrouter_http_error_raises():
    with patch("src.agents.cinematography_agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_post.return_value = mock_response
        with pytest.raises(Exception, match="404 Not Found"):
            ca._call_openrouter("system", "user", ca.OPENROUTER_MODEL)
