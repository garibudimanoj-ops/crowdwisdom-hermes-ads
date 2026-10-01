from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.video_agent import (
    VideoAgentError,
    _convert_storyboard_to_props,
    _load_storyboard,
    _render,
    run_video_agent,
)


# ---------- Test _convert_storyboard_to_props ----------
def test_convert_storyboard_empty() -> None:
    with pytest.raises(VideoAgentError, match="Storyboard has no scenes"):
        _convert_storyboard_to_props({})


def _make_composer(tmp_path: Path) -> Path:
    composer_dir = tmp_path / "composer"
    src_dir = composer_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "index.tsx").write_text("// dummy", encoding="utf-8")
    
    # Create node_modules/.bin directory with remotion CLI stubs
    bin_dir = composer_dir / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    
    # Create Windows-style .cmd stub
    windows_cli = bin_dir / "remotion.cmd"
    windows_cli.write_text("@echo off\necho \"Remotion CLI stub\"\n", encoding="utf-8")
    
    # Create Unix-style executable stub
    unix_cli = bin_dir / "remotion"
    unix_cli.write_text("#!/bin/sh\necho \"Remotion CLI stub\"\n", encoding="utf-8")
    unix_cli.chmod(0o755)  # Make executable
    
    return composer_dir


def _make_output_path(tmp_path: Path) -> Path:
    output_path = tmp_path / "outputs" / "videos" / "final_ad.mp4"
    output_path.parent.mkdir(parents=True)
    return output_path


# ---------- Test _load_storyboard ----------
def test_load_storyboard_success(tmp_path: Path) -> None:
    path = tmp_path / "storyboard.json"
    data = {"scenes": [{"id": "s1", "type": "text_card", "text": "Hello"}]}
    path.write_text(json.dumps(data), encoding="utf-8")
    result = _load_storyboard(path)
    assert result == data


def test_load_storyboard_not_found() -> None:
    with pytest.raises(VideoAgentError, match="Storyboard not found"):
        _load_storyboard(Path("no/such/file.json"))


def test_load_storyboard_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "storyboard.json"
    path.write_text("{ invalid json", encoding="utf-8")
    with pytest.raises(VideoAgentError, match="Invalid JSON"):
        _load_storyboard(path)


def test_load_storyboard_not_dict(tmp_path: Path) -> None:
    path = tmp_path / "storyboard.json"
    path.write_text("[\"not\", \"a\", \"dict\"]", encoding="utf-8")
    with pytest.raises(VideoAgentError, match="Storyboard must be a JSON object"):
        _load_storyboard(path)


# ---------- Test _convert_storyboard_to_props ----------
def test_convert_storyboard_text_card() -> None:
    storyboard = {
        "scenes": [
            {
                "id": "title",
                "type": "text_card",
                "text": "Hello World",
                "start_seconds": 0,
                "end_seconds": 5,
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    assert props["theme"] == "flat-motion-graphics"
    assert len(props["cuts"]) == 1
    cut = props["cuts"][0]
    assert cut["id"] == "title"
    assert cut["type"] == "text_card"
    assert cut["in_seconds"] == 0
    assert cut["out_seconds"] == 5
    assert cut["text"] == "Hello World"
    assert cut["backgroundColor"] == "#0F172A"


def test_convert_storyboard_stat_card() -> None:
    storyboard = {
        "scenes": [
            {
                "id": "stats",
                "type": "stat_card",
                "stat": "100K",
                "subtitle": "Users",
                "start_seconds": 5,
                "end_seconds": 10,
                "accent_color": "#FF0000",
                "background_color": "#FFFFFF",
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    cut = props["cuts"][0]
    assert cut["type"] == "stat_card"
    assert cut["stat"] == "100K"
    assert cut["subtitle"] == "Users"
    assert cut["accentColor"] == "#FF0000"
    assert cut["backgroundColor"] == "#FFFFFF"


def test_convert_storyboard_bar_chart() -> None:
    storyboard = {
        "scenes": [
            {
                "id": "chart",
                "type": "bar_chart",
                "title": "Sales",
                "data": [{"label": "Q1", "value": 10}, {"label": "Q2", "value": 20}],
                "start_seconds": 10,
                "end_seconds": 20,
                "colors": ["#FF0000", "#00FF00"],
                "show_grid": False,
                "show_values": False,
                "background_color": "#000000",
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    cut = props["cuts"][0]
    assert cut["type"] == "bar_chart"
    assert cut["title"] == "Sales"
    assert cut["chartData"] == [{"label": "Q1", "value": 10}, {"label": "Q2", "value": 20}]
    assert cut["chartColors"] == ["#FF0000", "#00FF00"]
    assert cut["showGrid"] is False
    assert cut["showValues"] is False
    assert cut["backgroundColor"] == "#000000"


def test_convert_storyboard_overlay() -> None:
    storyboard = {
        "scenes": [
            {
                "id": "s1",
                "type": "text_card",
                "text": "Main",
                "start_seconds": 0,
                "end_seconds": 5,
                "overlay": "Highlight",
                "overlay_type": "section_title",
                "overlay_subtitle": "Important",
                "overlay_position": "top-left",
                "accent_color": "#F00",
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    assert len(props["cuts"]) == 1
    assert len(props["overlays"]) == 1
    overlay = props["overlays"][0]
    assert overlay["type"] == "section_title"
    assert overlay["text"] == "Highlight"
    assert overlay["subtitle"] == "Important"
    assert overlay["position"] == "top-left"
    assert overlay["accentColor"] == "#F00"


# ---------- Test aspect ratio conversion (1920x1080 -> 1080x1920) ----------
def test_convert_storyboard_aspect_ratio_landscape_to_portrait() -> None:
    """Test that landscape 1920x1080 dimensions are converted to portrait 1080x1920."""
    storyboard = {
        "scenes": [
            {
                "id": "s1",
                "type": "text_card",
                "text": "Test",
                "start_seconds": 0,
                "end_seconds": 5,
                "width": 1920,
                "height": 1080,
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    # The conversion should swap width and height
    cut = props["cuts"][0]
    # The converted dimensions should be 1080x1920 (portrait)
    assert cut.get("width") == 1080
    assert cut.get("height") == 1920


def test_convert_storyboard_aspect_ratio_already_portrait() -> None:
    """Test that already portrait 1080x1920 dimensions remain unchanged."""
    storyboard = {
        "scenes": [
            {
                "id": "s1",
                "type": "text_card",
                "text": "Test",
                "start_seconds": 0,
                "end_seconds": 5,
                "width": 1080,
                "height": 1920,
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    cut = props["cuts"][0]
    # Dimensions should remain 1080x1920
    assert cut.get("width") == 1080
    assert cut.get("height") == 1920


def test_convert_storyboard_aspect_ratio_square() -> None:
    """Test that square dimensions are handled correctly."""
    storyboard = {
        "scenes": [
            {
                "id": "s1",
                "type": "text_card",
                "text": "Test",
                "start_seconds": 0,
                "end_seconds": 5,
                "width": 1080,
                "height": 1080,
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    cut = props["cuts"][0]
    # Square should remain square
    assert cut.get("width") == 1080
    assert cut.get("height") == 1080


def test_convert_storyboard_aspect_ratio_no_dimensions() -> None:
    """Test that missing dimensions default to portrait 1080x1920."""
    storyboard = {
        "scenes": [
            {
                "id": "s1",
                "type": "text_card",
                "text": "Test",
                "start_seconds": 0,
                "end_seconds": 5,
            }
        ]
    }
    props = _convert_storyboard_to_props(storyboard)
    cut = props["cuts"][0]
    # Should default to 1080x1920
    assert cut.get("width") == 1080
    assert cut.get("height") == 1920


# ---------- Test _render (mocked) ----------
def test_render_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    props = {"theme": "test", "cuts": []}
    output_path = _make_output_path(tmp_path)
    composer_dir = _make_composer(tmp_path)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = b""
    mock_run.return_value.stderr = b""

    monkeypatch.setattr("subprocess.run", mock_run)

    result = _render(props, output_path, composer_dir)
    assert mock_run.called
    args, kwargs = mock_run.call_args
    # First argument should be the local CLI path (either .cmd or executable)
    cli_path = args[0][0]
    assert cli_path.endswith("remotion.cmd") or cli_path.endswith("remotion")
    assert args[0][1] == "render"
    assert args[0][2] == "src/index.tsx"
    assert args[0][3] == "CinematicStoryboard"
    # Output path passed to subprocess must be absolute
    output_arg = [a for a in args[0] if a.endswith(".mp4")][0]
    assert Path(output_arg).is_absolute(), f"Output path must be absolute, got: {output_arg}"
    # Check for Windows-safe combined arg format: --props=<absolute-path>
    props_args = [a for a in args[0] if a.startswith("--props")]
    assert len(props_args) == 1
    assert props_args[0].startswith("--props=")
    props_path_str = props_args[0].split("=", 1)[1]
    assert Path(props_path_str).is_absolute(), f"Props path must be absolute, got: {props_path_str}"
    assert "_props.json" in props_path_str
    assert "--codec" in args[0]
    assert "h264" in args[0]
    # cwd must be the composer directory
    assert kwargs.get("cwd") == composer_dir


def test_render_props_arg_format(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify subprocess command uses --props=<path> (Windows-safe single arg)."""
    props = {"theme": "test", "cuts": []}
    output_path = _make_output_path(tmp_path)
    composer_dir = _make_composer(tmp_path)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = b""
    mock_run.return_value.stderr = b""

    monkeypatch.setattr("subprocess.run", mock_run)

    _render(props, output_path, composer_dir)
    args, kwargs = mock_run.call_args
    cmd = args[0]

    # First argument should be the local CLI path
    cli_path = cmd[0]
    assert cli_path.endswith("remotion.cmd") or cli_path.endswith("remotion")
    # Ensure --props=<path> exists as a single argument
    props_args = [a for a in cmd if a.startswith("--props=")]
    assert len(props_args) == 1, f"Expected exactly one --props= arg, got: {props_args}"
    # Verify the path is included in the arg and is absolute
    props_path_str = props_args[0].split("=", 1)[1]
    assert Path(props_path_str).is_absolute(), f"Props path must be absolute, got: {props_path_str}"
    assert "_props.json" in props_path_str
    # cwd must be the composer directory
    assert kwargs.get("cwd") == composer_dir


def test_render_local_cli_not_found(tmp_path: Path) -> None:
    """Test error when local Remotion CLI is not found."""
    composer_dir = tmp_path / "composer"
    src_dir = composer_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "index.tsx").write_text("// dummy", encoding="utf-8")
    # No node_modules/.bin/remotion* created
    
    output_path = _make_output_path(tmp_path)
    
    with pytest.raises(VideoAgentError, match="Local Remotion CLI not found"):
        _render({}, output_path, composer_dir)


def test_render_composer_missing_index(tmp_path: Path) -> None:
    with pytest.raises(VideoAgentError, match="OpenMontage composer not found"):
        _render({}, tmp_path / "out.mp4", tmp_path)


def test_render_subprocess_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    composer_dir = _make_composer(tmp_path)
    output_path = _make_output_path(tmp_path)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = b"Render failed: out of memory"
    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(VideoAgentError, match="OpenMontage render failed"):
        _render({}, output_path, composer_dir)


# ---------- Test run_video_agent ----------
def test_run_video_agent_dry_run() -> None:
    result = run_video_agent(mode="dry_run")
    assert result["status"] == "completed"
    assert result["mode"] == "dry_run"
    assert "note" in result["outputs"]
    assert "video_mp4" in result["outputs"]


def test_run_video_agent_live_missing_storyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_MODE", "live")
    with pytest.raises(VideoAgentError, match="Storyboard not found"):
        run_video_agent(storyboard_path=Path("no/such/storyboard.json"))


def test_run_video_agent_live_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "s1",
                        "type": "text_card",
                        "text": "Test",
                        "start_seconds": 0,
                        "end_seconds": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = _make_output_path(tmp_path)
    composer_dir = _make_composer(tmp_path)

    # Create dummy MP4 file that the function will check for
    output_path.write_bytes(b"fake mp4")

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = b""
    mock_run.return_value.stderr = b""

    monkeypatch.setattr("os.environ.get", lambda k, d: "live")
    monkeypatch.setattr("subprocess.run", mock_run)

    result = run_video_agent(
        storyboard_path=storyboard_path,
        output_path=output_path,
        composer_dir=composer_dir,
    )

    assert result["status"] == "completed"
    assert result["mode"] == "live"
    assert result["outputs"]["video_mp4"] == str(output_path)
    assert mock_run.called


def test_run_video_agent_live_render_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "s1",
                        "type": "text_card",
                        "text": "Test",
                        "start_seconds": 0,
                        "end_seconds": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = _make_output_path(tmp_path)
    composer_dir = _make_composer(tmp_path)

    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = b"something went wrong"

    monkeypatch.setattr("os.environ.get", lambda k, d: "live")
    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(VideoAgentError, match="OpenMontage render failed"):
        run_video_agent(
            storyboard_path=storyboard_path,
            output_path=output_path,
            composer_dir=composer_dir,
        )


# ---------- Integration test for full pipeline ----------
def test_run_video_agent_integration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "hook",
                        "type": "hero_title",
                        "text": "OpenMontage Test",
                        "subtitle": "Testing video integration",
                        "start_seconds": 0,
                        "end_seconds": 3,
                        "background_color": "#0F172A",
                    },
                    {
                        "id": "stat",
                        "type": "stat_card",
                        "stat": "100%",
                        "subtitle": "Success rate",
                        "start_seconds": 3,
                        "end_seconds": 8,
                        "accent_color": "#22D3EE",
                        "background_color": "#0F172A",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = _make_output_path(tmp_path)
    composer_dir = _make_composer(tmp_path)

    # Create dummy MP4 file that the function will check for
    output_path.write_bytes(b"fake mp4")

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = b""
    mock_run.return_value.stderr = b""

    monkeypatch.setattr("os.environ.get", lambda k, d: "live")
    monkeypatch.setattr("subprocess.run", mock_run)

    result = run_video_agent(
        storyboard_path=storyboard_path,
        output_path=output_path,
        composer_dir=composer_dir,
    )

    assert result["status"] == "completed"
    assert result["mode"] == "live"
    assert "video_mp4" in result["outputs"]
    assert result["outputs"]["video_mp4"] == str(output_path)