import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.preflight import (
    run_preflight,
    write_preflight_report,
    _check_env_var,
    _check_python_module,
    _check_executable,
    _check_path_exists,
    _check_output_dir,
    _check_artifact,
    _check_unique_data,
    _check_manifest_readable,
    _check_status_artifact_readable,
    _check_not_locked,
    PreflightError,
)


class TestEnvChecks:
    def test_env_var_present(self):
        with patch.dict(os.environ, {"TEST_VAR": "some_value"}):
            result = _check_env_var("TEST_VAR")
        assert result["status"] == "pass"
        assert "present" in result["detail"]

    def test_env_var_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _check_env_var("MISSING_VAR")
        assert result["status"] == "fail"
        assert "missing" in result["detail"]


class TestPythonChecks:
    def test_python_module_importable(self):
        result = _check_python_module("json")
        assert result["status"] == "pass"
        assert "importable" in result["detail"]

    def test_python_module_not_importable(self):
        result = _check_python_module("nonexistent_module_xyz")
        assert result["status"] == "fail"
        assert "not importable" in result["detail"]


class TestExecutableChecks:
    def test_executable_found(self):
        result = _check_executable("python")
        assert result["status"] == "pass"
        assert "found on PATH" in result["detail"]

    def test_executable_not_found(self):
        result = _check_executable("nonexistent_executable_xyz")
        assert result["status"] == "fail"
        assert "not found on PATH" in result["detail"]


class TestPathChecks:
    def test_path_exists(self, tmp_path):
        test_file = tmp_path / "exists.txt"
        test_file.write_text("content")
        result = _check_path_exists("test_file", test_file)
        assert result["status"] == "pass"
        assert "exists" in result["detail"]

    def test_path_missing(self, tmp_path):
        missing = tmp_path / "missing.txt"
        result = _check_path_exists("missing", missing)
        assert result["status"] == "fail"
        assert "does not exist" in result["detail"]


class TestOutputDirChecks:
    def test_output_dir_exists(self, tmp_path):
        dir_path = tmp_path / "output" / "dir"
        dir_path.mkdir(parents=True, exist_ok=True)
        result = _check_output_dir("test_dir", dir_path)
        assert result["status"] == "pass"

    def test_output_dir_missing(self, tmp_path):
        dir_path = tmp_path / "missing_dir"
        result = _check_output_dir("missing_dir", dir_path)
        assert result["status"] == "warning"
        assert "does not exist" in result["detail"]


class TestArtifactChecks:
    def test_artifact_exists(self, tmp_path):
        file_path = tmp_path / "artifact.json"
        file_path.write_text('{"test": true}')
        result = _check_artifact("test_artifact", file_path)
        assert result["status"] == "pass"
        assert "exists" in result["detail"]

    def test_artifact_missing(self, tmp_path):
        file_path = tmp_path / "missing.json"
        result = _check_artifact("missing_artifact", file_path)
        assert result["status"] == "fail"
        assert "does not exist" in result["detail"]


class TestUniqueDataChecks:
    def test_unique_data_missing_dir(self, tmp_path):
        # data/unique_data doesn't exist
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_unique_data()
        assert result["status"] == "warning"
        assert "does not exist" in result["detail"]

    def test_unique_data_empty_dir(self, tmp_path):
        # data/unique_data exists but is empty
        unique_dir = tmp_path / "data" / "unique_data"
        unique_dir.mkdir(parents=True, exist_ok=True)
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_unique_data()
        assert result["status"] == "warning"
        assert "no JSON files" in result["detail"]

    def test_unique_data_has_files(self, tmp_path):
        # data/unique_data has JSON files
        unique_dir = tmp_path / "data" / "unique_data"
        unique_dir.mkdir(parents=True, exist_ok=True)
        (unique_dir / "data1.json").write_text('{}')
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_unique_data()
        assert result["status"] == "pass"


class TestManifestChecks:
    def test_manifest_not_found(self, tmp_path):
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_manifest_readable()
        assert result["status"] == "warning"
        assert "not found" in result["detail"]

    def test_manifest_valid(self, tmp_path):
        manifest_path = tmp_path / "outputs" / "run_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"status": "ok"}))
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_manifest_readable()
        assert result["status"] == "pass"

    def test_manifest_malformed(self, tmp_path):
        manifest_path = tmp_path / "outputs" / "run_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text("invalid json")
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_manifest_readable()
        assert result["status"] == "fail"
        assert "malformed" in result["detail"]


class TestStatusArtifactChecks:
    def test_status_not_found(self, tmp_path):
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_status_artifact_readable()
        assert result["status"] == "warning"
        assert "not found" in result["detail"]

    def test_status_valid(self, tmp_path):
        status_path = tmp_path / "outputs" / "pipeline_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps({"status": "ok"}))
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_status_artifact_readable()
        assert result["status"] == "pass"

    def test_status_malformed(self, tmp_path):
        status_path = tmp_path / "outputs" / "pipeline_status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text("invalid json")
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_status_artifact_readable()
        assert result["status"] == "fail"
        assert "malformed" in result["detail"]


class TestLockedCheck:
    def test_not_locked(self, tmp_path):
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_not_locked()
        assert result["status"] == "pass"
        assert "No lock file" in result["detail"]

    def test_locked(self, tmp_path):
        lock_file = tmp_path / ".pipeline.lock"
        lock_file.touch()
        with patch("src.preflight.PROJECT_ROOT", tmp_path):
            result = _check_not_locked()
        assert result["status"] == "fail"
        assert "locked" in result["detail"]


class TestRunPreflight:
    def test_all_pass_scenario(self, tmp_path):
        # Set up a fully passing environment
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        (composer / "node_modules").mkdir()
        for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
            (tmp_path / d).mkdir(parents=True)
        (tmp_path / "data" / "unique_data").mkdir(parents=True)
        (tmp_path / "outputs" / "ads" / "ads.json").write_text('{}')
        (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
        (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
        (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
        (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()

        assert report["ready"] is True
        assert report["summary"]["fail"] == 0

    def test_missing_secret_fails(self, tmp_path):
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()
        assert report["ready"] is False
        assert report["summary"]["fail"] > 0

    def test_missing_node_fails(self, tmp_path):
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        (composer / "node_modules").mkdir()
        for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
            (tmp_path / d).mkdir(parents=True)
        (tmp_path / "outputs" / "ads" / "ads.json").write_text('{}')
        (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
        (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
        (tmp_path / "data" / "unique_data").mkdir(parents=True)
        (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
        (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: None if x == "node" else "/fake/path"
            report = run_preflight()
        assert report["ready"] is False
        assert report["summary"]["fail"] > 0

    def test_missing_npx_fails(self, tmp_path):
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        (composer / "node_modules").mkdir()
        for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
            (tmp_path / d).mkdir(parents=True)
        (tmp_path / "outputs" / "ads" / "ads.json").write_text('{}')
        (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
        (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
        (tmp_path / "data" / "unique_data").mkdir(parents=True)
        (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
        (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: None if x == "npx" else "/fake/path"
            report = run_preflight()
        assert report["ready"] is False
        assert report["summary"]["fail"] > 0

    def test_missing_ffprobe_fails(self, tmp_path):
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        (composer / "node_modules").mkdir()
        for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
            (tmp_path / d).mkdir(parents=True)
        (tmp_path / "outputs" / "ads" / "ads.json").write_text('{}')
        (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
        (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
        (tmp_path / "data" / "unique_data").mkdir(parents=True)
        (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
        (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: None if x == "ffprobe" else "/fake/path"
            report = run_preflight()
        assert report["ready"] is False
        assert report["summary"]["fail"] > 0

    def test_missing_openmontage_composer_fails(self, tmp_path):
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "nonexistent_composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()
        assert report["ready"] is False
        assert any("openmontage" in c["name"] for c in report["checks"] if c["status"] == "fail")

    def test_missing_composer_index_fails(self, tmp_path):
        composer = tmp_path / "composer"
        composer.mkdir()
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(composer),
            "CROWDWISDOM_URL": "https://test.com",
        }
        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()
        assert report["ready"] is False
        assert any("composer_index" in c["name"] for c in report["checks"] if c["status"] == "fail")

    def test_missing_node_modules_fails(self, tmp_path):
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(composer),
            "CROWDWISDOM_URL": "https://test.com",
        }
        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()
        assert report["ready"] is False
        assert any("composer_node_modules" in c["name"] for c in report["checks"] if c["status"] == "fail")

    def test_missing_required_artifact_fails(self, tmp_path):
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        (composer / "node_modules").mkdir()
        for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
            (tmp_path / d).mkdir(parents=True)
        # Missing ads.json artifact
        (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
        (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
        (tmp_path / "data" / "unique_data").mkdir(parents=True)
        (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
        (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()
        assert report["ready"] is False
        assert report["summary"]["fail"] > 0

    def test_no_unique_data_warning(self, tmp_path):
        (tmp_path / "data" / "unique_data").mkdir(parents=True)
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        (composer / "node_modules").mkdir()
        for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
            (tmp_path / d).mkdir(parents=True)
        (tmp_path / "outputs" / "ads" / "ads.json").write_text('{}')
        (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
        (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
        (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
        (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()
        assert report["ready"] is True
        assert any(c["status"] == "warning" and "unique_data" in c["name"] for c in report["checks"])

    def test_locked_pipeline_fails(self, tmp_path):
        lock_file = tmp_path / ".pipeline.lock"
        lock_file.touch()
        env_vars = {
            "OPENROUTER_API_KEY": "test",
            "APIFY_API_TOKEN": "test",
            "TAVILY_API_KEY": "test",
            "EXA_API_KEY": "test",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }
        composer = tmp_path / "composer"
        (composer / "src").mkdir(parents=True)
        (composer / "src" / "index.tsx").write_text("// test")
        (composer / "node_modules").mkdir()
        for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
            (tmp_path / d).mkdir(parents=True)
        (tmp_path / "outputs" / "ads" / "ads.json").write_text('{}')
        (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
        (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
        (tmp_path / "data" / "unique_data").mkdir(parents=True)
        (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
        (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

        with patch.dict(os.environ, env_vars, clear=False), \
             patch("src.preflight.PROJECT_ROOT", tmp_path), \
             patch("src.preflight.load_dotenv"), \
             patch("src.preflight.shutil.which", return_value="/fake/path"):
            report = run_preflight()
        assert report["ready"] is False
        assert any("not_locked" in c["name"] for c in report["checks"] if c["status"] == "fail")


class TestSecretRedaction:
    def test_no_secrets_in_report(self, tmp_path):
        # Verify secret values never appear in the report
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "secret-key-123",
            "APIFY_API_TOKEN": "secret-token-456",
            "TAVILY_API_KEY": "secret-tavily",
            "EXA_API_KEY": "secret-exa",
            "OPENROUTER_MODEL": "test",
            "OPENMONTAGE_PATH": str(tmp_path / "composer"),
            "CROWDWISDOM_URL": "https://test.com",
        }), patch("src.preflight.shutil.which") as mock_which:
            mock_which.return_value = "/fake/path"
            composer = tmp_path / "composer"
            (composer / "src").mkdir(parents=True)
            (composer / "src" / "index.tsx").write_text("// test")
            (composer / "node_modules").mkdir()
            for d in ["outputs/ads", "outputs/insights", "outputs/research"]:
                (tmp_path / d).mkdir(parents=True)
            (tmp_path / "outputs" / "ads" / "ads.json").write_text('{}')
            (tmp_path / "outputs" / "insights" / "marketing_insights.json").write_text('{}')
            (tmp_path / "outputs" / "research" / "research.json").write_text('{}')
            (tmp_path / "data" / "unique_data").mkdir(parents=True)
            (tmp_path / "data" / "unique_data" / "data.json").write_text('{}')
            (tmp_path / "outputs" / "run_manifest.json").write_text('{}')
            (tmp_path / "outputs" / "pipeline_status.json").write_text('{}')

            with patch("src.preflight.PROJECT_ROOT", tmp_path):
                report = run_preflight()

        # Convert to JSON and verify no secrets appear
        report_str = json.dumps(report)
        assert "secret-key-123" not in report_str
        assert "secret-token-456" not in report_str
        assert "secret-tavily" not in report_str
        assert "secret-exa" not in report_str


class TestWritePreflightReport:
    def test_write_report(self, tmp_path):
        report = {"ready": True, "checks": [], "summary": {"pass": 1, "warning": 0, "fail": 0}}
        output_path = tmp_path / "preflight_report.json"
        result = write_preflight_report(report, output_path)
        assert result == report
        assert output_path.exists()
        assert json.loads(output_path.read_text()) == report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])