"""Tests for Hermes Python backend."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.integrations.hermes_python_backend import (
    HermesPythonConfig,
    HermesPythonError,
    run_hermes_python,
)


class TestHermesPythonConfig:
    def test_default_values(self) -> None:
        config = HermesPythonConfig()
        assert config.model == "nvidia/nemotron-3-super-120b-a12b:free"
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.timeout == 300

    def test_from_env_overrides(self, monkeypatch) -> None:
        monkeypatch.setenv("HERMES_MODEL", "test/model")
        monkeypatch.setenv("HERMES_BASE_URL", "https://test.example.com/v1")
        monkeypatch.setenv("HERMES_TIMEOUT", "120")

        config = HermesPythonConfig.from_env()
        assert config.model == "test/model"
        assert config.base_url == "https://test.example.com/v1"
        assert config.timeout == 120


class TestRunHermesPython:
    def test_valid_config_validation(self) -> None:
        config = HermesPythonConfig(
            managed_python=r"C:\nonexistent\python.exe",
            worker_script=r"C:\nonexistent\worker.py",
        )

        with pytest.raises(RuntimeError, match="Managed Hermes Python not found"):
            run_hermes_python("test", config=config)

    def test_missing_worker_script(self) -> None:
        # Test that missing worker script raises proper error
        # We'll test this with actual file system check rather than mocking
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use non-existent paths in config
            config = HermesPythonConfig(
                managed_python=os.path.join(tmpdir, "nonexistent_python.exe"),
                worker_script=os.path.join(tmpdir, "nonexistent_worker.py"),
            )
            with pytest.raises(RuntimeError, match="Managed Hermes Python not found"):
                run_hermes_python("test", config=config)

    def test_empty_prompt_rejected(self) -> None:
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            run_hermes_python("   ")

    def test_mocked_successful_response(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"ok": True, "response": "Hello World"})
        mock_result.stderr = ""

        with patch("src.integrations.hermes_python_backend.subprocess.run", return_value=mock_result), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            response = run_hermes_python("test prompt", config=config)

        assert response == "Hello World"

    def test_mocked_worker_error(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"ok": False, "error": "AIAgent request failed"})
        mock_result.stderr = ""

        with patch("src.integrations.hermes_python_backend.subprocess.run", return_value=mock_result), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            with pytest.raises(HermesPythonError, match="Hermes Python backend failed: unknown"):
                run_hermes_python("test prompt", config=config)

    def test_mocked_malformed_json(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json"
        mock_result.stderr = ""

        with patch("src.integrations.hermes_python_backend.subprocess.run", return_value=mock_result), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            with pytest.raises(RuntimeError, match="Failed to parse worker output"):
                run_hermes_python("test prompt", config=config)

    def test_mocked_non_object_json(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(["not", "an", "object"])
        mock_result.stderr = ""

        with patch("src.integrations.hermes_python_backend.subprocess.run", return_value=mock_result), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            with pytest.raises(RuntimeError, match="not a JSON object"):
                run_hermes_python("test prompt", config=config)

    def test_mocked_empty_response(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"ok": True, "response": ""})
        mock_result.stderr = ""

        with patch("src.integrations.hermes_python_backend.subprocess.run", return_value=mock_result), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            with pytest.raises(RuntimeError, match="empty response"):
                run_hermes_python("test prompt", config=config)

    def test_mocked_missing_ok_field(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"ok": False})
        mock_result.stderr = ""

        with patch("src.integrations.hermes_python_backend.subprocess.run", return_value=mock_result), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            with pytest.raises(HermesPythonError, match="Hermes Python backend failed: unknown"):
                run_hermes_python("test prompt", config=config)

    def test_mocked_timeout(self) -> None:
        with patch("src.integrations.hermes_python_backend.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("cmd", 300)), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
                timeout=300,
            )
            with pytest.raises(RuntimeError, match="timed out after 300 seconds"):
                run_hermes_python("test prompt", config=config)

    def test_mocked_os_error(self) -> None:
        with patch("src.integrations.hermes_python_backend.subprocess.run",
                   side_effect=OSError("permission denied")), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            with pytest.raises(RuntimeError, match="Failed to start managed Python"):
                run_hermes_python("test prompt", config=config)

    def test_mocked_nonzero_exit(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "some error"

        with patch("src.integrations.hermes_python_backend.subprocess.run", return_value=mock_result), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            with pytest.raises(RuntimeError, match="exited with code 1"):
                run_hermes_python("test prompt", config=config)

    def test_system_prompt_forwarding(self) -> None:
        captured_input = {}

        def capture_run(*args, **kwargs):
            captured_input["input"] = kwargs.get("input", "")
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = json.dumps({"ok": True, "response": "OK"})
            mock.stderr = ""
            return mock

        with patch("src.integrations.hermes_python_backend.subprocess.run", side_effect=capture_run), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            run_hermes_python("user prompt", system_prompt="system prompt", config=config)

        parsed = json.loads(captured_input["input"])
        assert parsed["prompt"] == "user prompt"
        assert parsed["system_prompt"] == "system prompt"

    def test_system_prompt_none(self) -> None:
        captured_input = {}

        def capture_run(*args, **kwargs):
            captured_input["input"] = kwargs.get("input", "")
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = json.dumps({"ok": True, "response": "OK"})
            mock.stderr = ""
            return mock

        with patch("src.integrations.hermes_python_backend.subprocess.run", side_effect=capture_run), \
             patch("pathlib.Path.exists", return_value=True):
            config = HermesPythonConfig(
                managed_python=r"C:\fake\python.exe",
                worker_script=r"C:\fake\worker.py",
            )
            run_hermes_python("user prompt", system_prompt=None, config=config)

        parsed = json.loads(captured_input["input"])
        assert parsed["system_prompt"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])