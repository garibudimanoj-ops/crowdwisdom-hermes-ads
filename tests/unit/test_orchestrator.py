"""Tests for the orchestrator pipeline."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator import (
    Orchestrator,
    PipelineManifest,
    PipelineStatus,
)


class TestPipelineManifest:
    def test_default_creation(self) -> None:
        manifest = PipelineManifest(execution_mode="live", started_at="2026-01-01T00:00:00+00:00")
        assert manifest.execution_mode == "live"
        assert manifest.started_at == "2026-01-01T00:00:00+00:00"
        assert manifest.completed_at is None
        assert manifest.overall_status == PipelineStatus.PENDING
        assert manifest.stages == []
        assert manifest.output_paths == {}
        assert manifest.errors == {}
        assert manifest.blockers == []

    def test_to_dict(self) -> None:
        manifest = PipelineManifest(
            execution_mode="dry_run",
            started_at="2026-01-01T00:00:00+00:00",
            overall_status=PipelineStatus.COMPLETED,
        )
        d = manifest.to_dict()
        assert d["execution_mode"] == "dry_run"
        assert d["overall_status"] == "completed"
        assert "stages" in d

    def test_from_dict(self) -> None:
        data = {
            "execution_mode": "dry_run",
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:01:00+00:00",
            "overall_status": "completed",
            "stages": [{"stage": "ads", "status": "completed"}],
            "output_paths": {},
            "errors": {},
            "blockers": [],
        }
        manifest = PipelineManifest.from_dict(data)
        assert manifest.execution_mode == "dry_run"
        assert manifest.overall_status == PipelineStatus.COMPLETED


class TestOrchestratorDryRun:
    def test_dry_run_mode_initializes(self) -> None:
        orch = Orchestrator(mode="dry_run")
        assert orch.mode == "dry_run"
        assert orch.manifest.execution_mode == "dry_run"

    def test_live_mode_initializes(self) -> None:
        orch = Orchestrator(mode="live")
        assert orch.mode == "live"

    def test_env_var_mode(self) -> None:
        os.environ["PIPELINE_MODE"] = "dry_run"
        try:
            orch = Orchestrator()
            assert orch.mode == "dry_run"
        finally:
            os.environ.pop("PIPELINE_MODE", None)


class TestStageStatus:
    def test_stage_order(self) -> None:
        orch = Orchestrator()
        assert orch.STAGE_ORDER == [
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

    def test_stage_dependencies(self) -> None:
        orch = Orchestrator()
        assert orch.STAGE_DEPS["marketing"] == ["ads"]
        assert orch.STAGE_DEPS["script"] == ["data"]
        assert orch.STAGE_DEPS["creative_dir"] == ["script"]
        assert orch.STAGE_DEPS["video"] == ["storyboard"]
        assert orch.STAGE_DEPS["quality"] == ["video"]


class TestOrchestratorDryRunExecution:
    def test_dry_run_executes_all_stages(self) -> None:
        """Test dry-run executes through all stages without live calls."""
        orch = Orchestrator(mode="dry_run")

        # Mock the first 5 stages to avoid real API calls
        with patch.object(orch, "run_ads", return_value={"status": "completed"}), \
             patch.object(orch, "run_marketing", return_value={"status": "completed"}), \
             patch.object(orch, "run_research", return_value={"status": "completed"}), \
             patch.object(orch, "run_data", return_value={"status": "completed"}):
            result = orch.run()

        # All stages should be present in results
        for stage in orch.STAGE_ORDER:
            assert stage in orch.stage_results, f"Stage {stage} missing from results"

        # First 5 should complete in dry_run
        assert orch.stage_results["ads"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["marketing"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["research"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["data"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["script"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["script"]["mode"] == "dry_run"

        # Downstream stages should also complete in dry_run
        assert orch.stage_results["creative_dir"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["storyboard"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["video"]["status"] == PipelineStatus.COMPLETED.value
        assert orch.stage_results["quality"]["status"] == PipelineStatus.COMPLETED.value

    def test_dry_run_manifest_created(self) -> None:
        """Test that run_manifest.json is created in dry-run."""
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                orch = Orchestrator(mode="dry_run")

                with patch.object(orch, "run_ads", return_value={"status": "completed"}), \
                     patch.object(orch, "run_marketing", return_value={"status": "completed"}), \
                     patch.object(orch, "run_research", return_value={"status": "completed"}), \
                     patch.object(orch, "run_data", return_value={"status": "completed"}):
                    result = orch.run()

                manifest_path = Path("outputs/run_manifest.json")
                assert manifest_path.exists()

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                assert manifest["execution_mode"] == "dry_run"
                assert manifest["overall_status"] == "completed"
                assert len(manifest["stages"]) == 9
            finally:
                os.chdir(orig_cwd)

    def test_blocked_propagation(self) -> None:
        """Test that blocked stages propagate correctly."""
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                orch = Orchestrator(mode="live")

                # Make ads fail
                with patch.object(orch, "run_ads", return_value={"status": "failed"}), \
                     patch.object(orch, "run_marketing", return_value={"status": "completed"}), \
                     patch.object(orch, "run_research", return_value={"status": "completed"}), \
                     patch.object(orch, "run_data", return_value={"status": "completed"}):
                    result = orch.run()

                # Ads failed, marketing should be blocked
                assert orch.stage_results["ads"]["status"] == PipelineStatus.FAILED.value
                assert orch.stage_results["marketing"]["status"] == PipelineStatus.BLOCKED.value
                assert orch.stage_results["script"]["status"] == PipelineStatus.BLOCKED.value
                assert orch.stage_results["creative_dir"]["status"] == PipelineStatus.BLOCKED.value
            finally:
                os.chdir(orig_cwd)

    def test_script_blocked_propagates(self) -> None:
        """Test that script blocked propagates downstream."""
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                orch = Orchestrator(mode="live")

                with patch.object(orch, "run_ads", return_value={"status": "completed"}), \
                     patch.object(orch, "run_marketing", return_value={"status": "completed"}), \
                     patch.object(orch, "run_research", return_value={"status": "completed"}), \
                     patch.object(orch, "run_data", return_value={"status": "completed"}), \
                     patch.object(orch, "run_script", return_value={"status": "blocked", "error": "rate limit"}):
                    result = orch.run()

                assert orch.stage_results["script"]["status"] == PipelineStatus.BLOCKED.value
                assert orch.stage_results["creative_dir"]["status"] == PipelineStatus.BLOCKED.value
                assert orch.stage_results["storyboard"]["status"] == PipelineStatus.BLOCKED.value
                assert orch.stage_results["video"]["status"] == PipelineStatus.BLOCKED.value
                assert orch.stage_results["quality"]["status"] == PipelineStatus.BLOCKED.value
            finally:
                os.chdir(orig_cwd)

    def test_script_failed_propagates(self) -> None:
        """Test that script failed (not blocked) also propagates."""
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                orch = Orchestrator(mode="live")

                with patch.object(orch, "run_ads", return_value={"status": "completed"}), \
                     patch.object(orch, "run_marketing", return_value={"status": "completed"}), \
                     patch.object(orch, "run_research", return_value={"status": "completed"}), \
                     patch.object(orch, "run_data", return_value={"status": "completed"}), \
                     patch.object(orch, "run_script", return_value={"status": "failed", "error": "unexpected error"}):
                    result = orch.run()

                assert orch.stage_results["script"]["status"] == PipelineStatus.FAILED.value
                assert orch.stage_results["creative_dir"]["status"] == PipelineStatus.BLOCKED.value
            finally:
                os.chdir(orig_cwd)


class TestManifestContents:
    def test_manifest_has_required_fields(self) -> None:
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                orch = Orchestrator(mode="dry_run")

                with patch.object(orch, "run_ads", return_value={"status": "completed"}), \
                     patch.object(orch, "run_marketing", return_value={"status": "completed"}), \
                     patch.object(orch, "run_research", return_value={"status": "completed"}), \
                     patch.object(orch, "run_data", return_value={"status": "completed"}):
                    orch.run()

                with open("outputs/run_manifest.json", "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                assert "execution_mode" in manifest
                assert "started_at" in manifest
                assert "completed_at" in manifest
                assert "overall_status" in manifest
                assert "stages" in manifest
                assert "output_paths" in manifest
                assert "errors" in manifest
                assert "blockers" in manifest

                for stage in manifest["stages"]:
                    assert "stage" in stage
                    assert "status" in stage
                    assert "started_at" in stage
                    assert "completed_at" in stage
                    assert "outputs" in stage
                    assert "error" in stage
            finally:
                os.chdir(orig_cwd)

    def test_run_script_fallback_to_unique_data_json_when_no_in_memory_result(
        self,
    ) -> None:
        """Test that run_script() reads unique_data.json when no in-memory data result exists.

        This simulates a standalone run_script() call in a separate process where
        self.stage_results["data"] is unavailable, so the orchestrator falls back to
        reading data/processed/unique_data.json to determine if Concept 2 should be blocked.
        """
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                # Setup: create the processed unique_data.json with no_data_available status
                processed_path = Path("data/processed/unique_data.json")
                processed_path.parent.mkdir(parents=True, exist_ok=True)
                with open(processed_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "metadata": {"status": "no_data_available"},
                            "records": [],
                            "unique_data_available": False,
                        },
                        f,
                    )

                orch = Orchestrator(mode="live")

                # Run data stage to ensure file exists
                with patch.object(orch, "run_ads", return_value={"status": "completed"}), \
                     patch.object(orch, "run_marketing", return_value={"status": "completed"}), \
                     patch.object(orch, "run_research", return_value={"status": "completed"}), \
                     patch.object(orch, "run_data", return_value={"status": "completed"}):
                    orch.run_data()

                # Verify the file exists and has the right content
                assert processed_path.exists()
                with open(processed_path, "r", encoding="utf-8") as f2:
                    re_read = json.load(f2)
                assert re_read["metadata"]["status"] == "no_data_available"

                # Now test run_script with mocked ScriptAgent and no in-memory data result.
                # self.stage_results["data"] is empty (simulating separate process).
                # The fallback should read unique_data.json and find no_data_available.
                from src.agents.script_agent import ScriptAgent, ScriptAgentError

                mock_script_agent = MagicMock()
                # Create concept_2.json in the mock output dir
                mock_output_dir = Path(tmpdir) / "outputs" / "scripts"
                mock_output_dir.mkdir(parents=True, exist_ok=True)
                concept_2_path = mock_output_dir / "concept_2.json"
                concept_2_path.write_text(
                    json.dumps({
                        "concept_id": 2,
                        "track": "unique_data",
                        "concept": {
                            "concept_id": 2,
                            "title": "Unique Data Concept (Blocked - No Data)",
                            "target_icp": "N/A",
                            "hook": "N/A",
                            "story": "N/A",
                            "scenes": [],
                            "narration": "",
                            "visual_direction": "",
                            "sound_direction": "",
                            "music_direction": "",
                            "minimal_text": "",
                            "cta": "Visit crowdwisdomtrading.com",
                            "duration": 0,
                            "evidence": [],
                        },
                    }),
                    encoding="utf-8",
                )
                concept_1_path = mock_output_dir / "concept_1.json"
                concept_1_path.write_text("{}")
                concept_3_path = mock_output_dir / "concept_3.json"
                concept_3_path.write_text("{}")

                mock_script_agent.output_dir = mock_output_dir
                mock_script_agent.run.return_value = {"status": "completed", "outputs": {}}

                with patch("src.orchestrator.ScriptAgent", return_value=mock_script_agent):
                    script_result = orch.run_script()

                # run_script should succeed (not blocked) because it read the file
                assert script_result["status"] == "completed"

                # Verify concept_2.json now has nested limitations
                if concept_2_path.exists():
                    with open(concept_2_path, "r", encoding="utf-8") as f3:
                        concept_2_data = json.load(f3)
                    # Should have nested concept.limitations set
                    limitations = concept_2_data.get("concept", {}).get(
                        "limitations", []
                    )
                    assert "Unique CrowdWisdom data is not available" in limitations
                else:
                    pytest.fail("concept_2.json was not created/modified")
            finally:
                os.chdir(orig_cwd)


class TestCreativeDirectorStandalone:
    """Tests for CreativeDirector stage when run standalone (separate process)."""

    def _make_valid_concept_json(self, path: Path, has_limitations: bool = False) -> None:
        """Write a valid concept JSON file to the given path."""
        limitations = ["Unique CrowdWisdom data is not available"] if has_limitations else []
        data = {
            "concept_id": 1,
            "track": "pain_icp",
            "concept": {
                "concept_id": 1,
                "title": "Test Concept",
                "target_icp": "N/A",
                "hook": "N/A",
                "story": "N/A",
                "scenes": [],
                "narration": "",
                "visual_direction": "",
                "sound_direction": "",
                "music_direction": "",
                "minimal_text": "",
                "cta": "Visit crowdwisdomtrading.com",
                "duration": 0,
                "evidence": [],
            },
        }
        if limitations:
            data["concept"]["limitations"] = limitations
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _make_malformed_concept_json(self, path: Path) -> None:
        """Write a malformed concept JSON file to the given path."""
        with path.open("w", encoding="utf-8") as f:
            f.write('{"invalid": json {')

    def test_in_process_script_result_allowed(self) -> None:
        """When run_creative_dir() has an in-memory script result, proceed normally."""
        orch = Orchestrator(mode="live")
        orch.stage_results["script"] = {
            "status": PipelineStatus.COMPLETED,
            "outputs": {
                "blocked_concepts": None,
                "viable_concepts": None,
            },
        }

        with patch("src.agents.creative_director.CreativeDirector") as mock_dir:
            mock_dir.return_value.run.return_value = {"status": "completed"}
            result = orch.run_creative_dir()
            assert result["status"] == "completed"

    def test_no_in_memory_result_all_concept_files_exist(self) -> None:
        """When no in-memory script result, but all three concept files exist on disk,
        allow Creative Director to proceed without rerunning ScriptAgent."""
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                scripts_dir = Path("outputs/scripts")
                scripts_dir.mkdir(parents=True, exist_ok=True)

                # Create all three valid concept files
                self._make_valid_concept_json(scripts_dir / "concept_1.json", has_limitations=False)
                self._make_valid_concept_json(scripts_dir / "concept_2.json", has_limitations=False)
                self._make_valid_concept_json(scripts_dir / "concept_3.json", has_limitations=False)

                orch = Orchestrator(mode="live")
                # No in-memory script result — stage_results["script"] is empty/falsy
                with patch("src.agents.creative_director.CreativeDirector") as mock_dir:
                    mock_dir.return_value.run.return_value = {"status": "completed"}
                    result = orch.run_creative_dir()

                # Should proceed because all files exist and are valid JSON
                assert result["status"] == "completed"
            finally:
                os.chdir(orig_cwd)

    def test_no_in_memory_result_missing_concept_file(self) -> None:
        """When no in-memory script result and a concept file is missing, block Creative Director."""
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                scripts_dir = Path("outputs/scripts")
                scripts_dir.mkdir(parents=True, exist_ok=True)

                # Only create 2 concept files; missing concept_3.json
                self._make_valid_concept_json(scripts_dir / "concept_1.json", has_limitations=False)
                self._make_valid_concept_json(scripts_dir / "concept_2.json", has_limitations=False)

                orch = Orchestrator(mode="live")
                result = orch.run_creative_dir()

                # Should be blocked because concept_3.json is missing
                assert result["status"] == "blocked"
                assert "artifacts incomplete" in result.get("reason", "").lower()
            finally:
                os.chdir(orig_cwd)

    def test_no_in_memory_result_malformed_concept_json(self) -> None:
        """When no in-memory script result and a concept file has malformed JSON, block Creative Director."""
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            try:
                scripts_dir = Path("outputs/scripts")
                scripts_dir.mkdir(parents=True, exist_ok=True)

                # Create valid concept_1.json and concept_3.json
                self._make_valid_concept_json(scripts_dir / "concept_1.json", has_limitations=False)
                self._make_valid_concept_json(scripts_dir / "concept_3.json", has_limitations=False)

                # Create malformed concept_2.json
                self._make_malformed_concept_json(scripts_dir / "concept_2.json")

                orch = Orchestrator(mode="live")
                result = orch.run_creative_dir()

                # Should be blocked because concept_2.json is malformed
                assert result["status"] == "blocked"
                assert "malformed" in result.get("reason", "").lower()
            finally:
                os.chdir(orig_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])