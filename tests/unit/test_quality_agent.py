import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.agents.quality_agent import (
    run_quality_agent,
    VideoAgentError,
)


def _create_mock_probe(duration=None, has_video=True, has_audio=True):
    streams = []
    if has_video:
        streams.append({
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1"
        })
    if has_audio:
        streams.append({
            "codec_type": "audio",
            "codec_name": "aac"
        })
    format_info = {
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "size": "1048576"
    }
    if duration is not None:
        format_info["duration"] = str(duration)
    return {"streams": streams, "format": format_info}


class TestDryRun:
    def test_dry_run_returns_completed(self):
        result = run_quality_agent(mode="dry_run")
        assert result["status"] == "completed"
        assert result["mode"] == "dry_run"
        assert "quality_report_json" in result["outputs"]
        assert "note" in result["outputs"]


class TestMissingFile:
    def test_missing_file_raises_error(self, tmp_path):
        missing_file = tmp_path / "missing.mp4"
        with pytest.raises(VideoAgentError, match="not found"):
            run_quality_agent(video_path=missing_file, mode="live")

    def test_zero_byte_file_raises_error(self, tmp_path):
        empty_file = tmp_path / "empty.mp4"
        empty_file.touch()
        with pytest.raises(VideoAgentError, match="is empty"):
            run_quality_agent(video_path=empty_file, mode="live")


class TestFfprobeErrors:
    def test_ffprobe_not_found(self, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"content")
        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(VideoAgentError, match="ffprobe not found"):
                run_quality_agent(video_path=video_file, mode="live")

    def test_ffprobe_failure(self, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"content")
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = b"Invalid data found"
        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            with pytest.raises(VideoAgentError, match="ffprobe failed"):
                run_quality_agent(video_path=video_file, mode="live")

    def test_malformed_probe_output(self, tmp_path):
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"content")
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"invalid json"
        mock_result.stderr = b""
        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            with pytest.raises(VideoAgentError, match="Malformed ffprobe output"):
                run_quality_agent(video_path=video_file, mode="live")


class TestValidVideo:
    def test_valid_video_passes(self, tmp_path):
        video_file = tmp_path / "valid.mp4"
        video_file.write_bytes(b"fake mp4 content" * 100)

        mock_probe = _create_mock_probe(duration=45.0, has_video=True, has_audio=True)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_probe).encode()
        mock_result.stderr = b""

        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = run_quality_agent(video_path=video_file, mode="live")

        assert result["status"] == "pass"
        assert result["mode"] == "live"
        assert "quality_report_json" in result["outputs"]
        assert result["outputs"]["quality_report_json"]
        # Check file was written with uppercase status in content
        report_path = Path(result["outputs"]["quality_report_json"])
        report_content = json.loads(report_path.read_text())
        assert report_content["status"] == "PASS"

    def test_valid_video_duration_in_range(self, tmp_path):
        video_file = tmp_path / "valid.mp4"
        video_file.write_bytes(b"content")

        mock_probe = _create_mock_probe(duration=45.0, has_video=True, has_audio=True)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_probe).encode()
        mock_result.stderr = b""

        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = run_quality_agent(video_path=video_file, mode="live")

        assert "Duration too short" not in str(result.get("errors", []))
        assert "Duration too long" not in str(result.get("errors", []))


class TestDurationValidation:
    def test_duration_below_30s_fails(self, tmp_path):
        video_file = tmp_path / "short.mp4"
        video_file.write_bytes(b"content")

        mock_probe = _create_mock_probe(duration=25.0, has_video=True, has_audio=True)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_probe).encode()
        mock_result.stderr = b""

        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = run_quality_agent(video_path=video_file, mode="live")

        assert result["status"] == "fail"
        assert any("too short" in e.lower() for e in result["errors"])

    def test_duration_above_60s_fails(self, tmp_path):
        video_file = tmp_path / "long.mp4"
        video_file.write_bytes(b"content")

        mock_probe = _create_mock_probe(duration=75.0, has_video=True, has_audio=True)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_probe).encode()
        mock_result.stderr = b""

        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = run_quality_agent(video_path=video_file, mode="live")

        assert result["status"] == "fail"
        assert any("too long" in e.lower() for e in result["errors"])


class TestStreamValidation:
    def test_missing_video_stream_fails(self, tmp_path):
        video_file = tmp_path / "audio_only.mp4"
        video_file.write_bytes(b"content")

        mock_probe = _create_mock_probe(duration=45.0, has_video=False, has_audio=True)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_probe).encode()
        mock_result.stderr = b""

        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = run_quality_agent(video_path=video_file, mode="live")

        assert result["status"] == "fail"
        assert any("No video stream" in e for e in result["errors"])

    def test_missing_audio_warns(self, tmp_path):
        video_file = tmp_path / "video_only.mp4"
        video_file.write_bytes(b"content")

        mock_probe = _create_mock_probe(duration=45.0, has_video=True, has_audio=False)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_probe).encode()
        mock_result.stderr = b""

        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = run_quality_agent(video_path=video_file, mode="live")

        # Warnings make it "warning", not "pass" or "fail"
        assert result["status"] == "warning"
        assert any("No audio stream" in w for w in result["warnings"])

    def test_low_fps_generates_warning(self, tmp_path):
        video_file = tmp_path / "low_fps.mp4"
        video_file.write_bytes(b"content")

        mock_probe = _create_mock_probe(duration=45.0, has_video=True, has_audio=True)
        # Set very low frame rate
        mock_probe["streams"][0]["r_frame_rate"] = "1/30"  # ~0.033 fps
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_probe).encode()
        mock_result.stderr = b""

        with patch("src.agents.quality_agent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            result = run_quality_agent(video_path=video_file, mode="live")

        assert result["status"] == "warning"
        assert any("Low frame rate" in w for w in result["warnings"])


class TestIntegration:
    def test_with_existing_smoke_test_video(self):
        video_path = Path("C:\\AI Projects\\crowdwisdom-hermes-ads\\outputs\\smoke-test\\demo-smoke-test.mp4")
        if not video_path.exists():
            pytest.skip("Smoke test video not found")

        # Test with actual video (23.06s duration - below 30s threshold)
        result = run_quality_agent(video_path=video_path, mode="live")
        assert result["status"] in ("fail", "warning")  # Duration < 30s
        assert any("too short" in e.lower() for e in result.get("errors", []))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])