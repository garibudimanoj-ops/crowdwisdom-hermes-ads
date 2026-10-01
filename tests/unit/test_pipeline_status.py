import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.status.pipeline_status import (
    get_pipeline_status,
    read_pipeline_status,
    write_pipeline_status,
    PipelineStatusError,
)


class TestReadPipelineStatus:
    def test_valid_manifest(self, tmp_path):
        # Create a valid manifest file
        manifest = {
            "execution_mode": "live",
            "overall_status": "completed",
            "started_at": "2026-09-25T19:41:58.124441+00:00",
            "completed_at": "2026-09-25T19:41:58.124788+00:00",
            "stages": [
                {
                    "stage": "ads",
                    "status": "completed",
                    "started_at": "2026-09-25T19:41:58.124469+00:00",
                    "completed_at": "2026-09-25T19:41:58.124490+00:00",
                    "outputs": {"ads_json": "outputs/ads/ads.json"},
                    "error": None,
                },
                {
                    "stage": "quality",
                    "status": "failed",
                    "started_at": "2026-09-25T19:41:58.124752+00:00",
                    "completed_at": "2026-09-25T19:41:58.124765+00:00",
                    "outputs": None,
                    "error": {"message": "Validation failed"},
                },
            ],
            "output_paths": {},
            "errors": {},
            "blockers": [],
        }

        manifest_path = tmp_path / "run_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        result = read_pipeline_status(manifest_path)

        assert result["execution_mode"] == "live"
        assert result["overall_status"] == "completed"
        assert len(result["stages"]) == 9  # All 9 stages represented

        # Check that stages have correct data
        ads_stage = next((s for s in result["stages"] if s["name"] == "ads"), None)
        assert ads_stage is not None
        assert ads_stage["name"] == "ads"
        assert ads_stage["status"] == "completed"
        assert ads_stage["outputs"]["ads_json"] == "outputs/ads/ads.json"

        quality_stage = next((s for s in result["stages"] if s["name"] == "quality"), None)
        assert quality_stage is not None
        assert quality_stage["name"] == "quality"
        assert quality_stage["status"] == "failed"
        assert quality_stage["error"]["message"] == "Validation failed"

        # Check that missing stages have pending status
        pending_stages = [s for s in result["stages"] if s["status"] == "pending"]
        assert len(pending_stages) > 0

        # Verify no secrets in output
        result_str = json.dumps(result)
        assert "api_key" not in result_str.lower()
        assert "password" not in result_str.lower()
        assert "token" not in result_str.lower()

    def test_manifest_not_found(self):
        missing_path = Path("/nonexistent/path/run_manifest.json")
        with pytest.raises(PipelineStatusError, match="Manifest not found"):
            read_pipeline_status(missing_path)

    def test_invalid_json_manifest(self, tmp_path):
        manifest_path = tmp_path / "run_manifest.json"
        manifest_path.write_text("invalid json")

        with pytest.raises(PipelineStatusError, match="Manifest is not valid JSON"):
            read_pipeline_status(manifest_path)

    def test_missing_stages(self, tmp_path):
        # Manifest with only some stages
        manifest = {
            "execution_mode": "live",
            "overall_status": "running",
            "started_at": "2026-09-25T19:41:58.124441+00:00",
            "completed_at": None,
            "stages": [
                {"stage": "ads", "status": "completed", "started_at": None, "completed_at": None, "outputs": None, "error": None},
            ],
            "output_paths": {},
            "errors": {},
            "blockers": [],
        }

        manifest_path = tmp_path / "run_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        result = read_pipeline_status(manifest_path)

        # Should have all 9 stages
        assert len(result["stages"]) == 9

        # ads should be completed, others pending
        ads_stage = next((s for s in result["stages"] if s["name"] == "ads"), None)
        assert ads_stage["status"] == "completed"

        # Script stage should be pending
        script_stage = next((s for s in result["stages"] if s["name"] == "script"), None)
        assert script_stage["status"] == "pending"

    def test_dry_run_mode(self, tmp_path):
        manifest = {
            "execution_mode": "dry_run",
            "overall_status": "completed",
            "started_at": "2026-09-25T19:41:58.124441+00:00",
            "completed_at": "2026-09-25T19:41:58.124788+00:00",
            "stages": [],
            "output_paths": {},
            "errors": {},
            "blockers": [],
        }

        manifest_path = tmp_path / "run_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        result = read_pipeline_status(manifest_path)

        assert result["execution_mode"] == "dry_run"
        assert result["overall_status"] == "completed"

    def test_stage_with_secrets(self, tmp_path):
        # Manifest with potentially sensitive data
        manifest = {
            "execution_mode": "live",
            "overall_status": "completed",
            "started_at": "2026-09-25T19:41:58.124441+00:00",
            "completed_at": None,
            "stages": [
                {
                    "stage": "data",
                    "status": "completed",
                    "started_at": None,
                    "completed_at": None,
                    "outputs": {"api_key": "secret123", "normal_data": "value"},
                    "error": None,
                }
            ],
            "output_paths": {},
            "errors": {"api_key": "invalid_key"},
            "blockers": [],
        }

        manifest_path = tmp_path / "run_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        result = read_pipeline_status(manifest_path)

        # Verify secrets are redacted
        data_str = json.dumps(result)
        assert "secret123" not in data_str
        assert "***REDACTED***" in data_str


class TestWritePipelineStatus:
    def test_write_valid_status(self, tmp_path):
        status = {
            "execution_mode": "live",
            "overall_status": "completed",
            "stages": [
                {"name": "ads", "status": "completed", "started_at": None, "completed_at": None, "outputs": {}, "error": None}
            ],
        }

        output_path = tmp_path / "pipeline_status.json"
        result = write_pipeline_status(status, output_path)

        assert result == status
        assert output_path.exists()

        # Verify content
        written_status = json.loads(output_path.read_text())
        assert written_status["execution_mode"] == "live"
        assert len(written_status["stages"]) == 1

    def test_write_default_path(self, tmp_path, monkeypatch):
        # Mock the read_pipeline_status to return predictable data
        mock_status = {
            "execution_mode": "live",
            "overall_status": "running",
            "stages": [],
        }

        with patch("src.status.pipeline_status.read_pipeline_status") as mock_read:
            mock_read.return_value = mock_status

            # Temporarily change current directory to tmp_path
            original_cwd = os.getcwd()
            monkeypatch.chdir(tmp_path)

            try:
                result = write_pipeline_status()
                assert result == mock_status

                # Should have written to outputs/pipeline_status.json
                expected_path = tmp_path / "outputs" / "pipeline_status.json"
                assert expected_path.exists()
            finally:
                monkeypatch.chdir(original_cwd)


class TestGetPipelineStatus:
    def test_get_with_default_paths(self, tmp_path, monkeypatch):
        manifest = {
            "execution_mode": "dry_run",
            "overall_status": "completed",
            "started_at": "2026-09-25T19:41:58.124441+00:00",
            "completed_at": None,
            "stages": [],
            "output_paths": {},
            "errors": {},
            "blockers": [],
        }

        manifest_path = tmp_path / "outputs" / "run_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest))

        status_artifact_path = tmp_path / "outputs" / "pipeline_status.json"

        # Mock the Path constructor to return our tmp_path
        with patch("src.status.pipeline_status.MANIFEST_PATH", manifest_path), \
             patch("src.status.pipeline_status.STATUS_ARTIFACT_PATH", status_artifact_path), \
             patch("src.status.pipeline_status.Path") as mock_path_class:

            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_text.return_value = json.dumps(manifest)
            mock_path_instance.parent.mkdir.return_value = None

            def path_constructor(path_str):
                if path_str == str(manifest_path):
                    return mock_path_instance
                if path_str == str(status_artifact_path):
                    return mock_path_instance
                return Path(path_str)

            mock_path_class.side_effect = path_constructor

            original_cwd = os.getcwd()
            monkeypatch.chdir(tmp_path)

            try:
                result = get_pipeline_status()

                assert result["execution_mode"] == "dry_run"
                assert result["overall_status"] == "completed"

                assert status_artifact_path.exists()
            finally:
                monkeypatch.chdir(original_cwd)

    def test_integration_with_real_manifest(self):
        # Test against the actual run_manifest.json we created in Phase 3
        manifest_path = Path(r"C:\AI Projects\crowdwisdom-hermes-ads\outputs\run_manifest.json")
        if manifest_path.exists():
            result = read_pipeline_status(manifest_path)

            assert result["execution_mode"] == "dry_run"
            assert result["overall_status"] == "completed"
            assert len(result["stages"]) == 9  # All 9 stages

            # Check that all stages are present
            stage_names = {stage["name"] for stage in result["stages"]}
            expected_stages = {
                "ads",
                "marketing",
                "research",
                "data",
                "script",
                "creative_dir",
                "storyboard",
                "video",
                "quality",
            }
            assert stage_names == expected_stages

            # Check that completed stages have correct status
            for stage in result["stages"]:
                if stage["name"] in ["ads", "marketing", "research", "data", "script", "creative_dir", "storyboard", "video", "quality"]:
                    assert stage["status"] == "completed"

            print(f"✓ Integration test passed: {len(result['stages'])} stages read from real manifest")
        else:
            pytest.skip("Real manifest not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])