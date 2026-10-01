from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from src.integrations.hermes_runner import HermesAgentRunner, HermesError
from src.integrations.hermes_python_backend import HermesPythonError


class TestHermesAgentRunnerCLI:
    """Tests for the CLI backend."""

    def test_runs_prompt_with_system_prompt(self) -> None:
        with patch("src.integrations.hermes_runner.shutil.which", return_value="/hermes"), \
             patch("src.integrations.hermes_runner.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(
                returncode=0,
                stdout="response ok",
                stderr=""
            )

            runner = HermesAgentRunner(timeout=120, backend="cli")
            response = runner.run(
                "Analyze this",
                system_prompt="You are a marketer.",
            )

            assert response == "response ok"
            assert mock_run.call_count == 1
            args = mock_run.call_args
            assert args[0][0][0] == "/hermes"
            assert args[0][0][1] == "-z"
            assert "SYSTEM INSTRUCTIONS" in args[0][0][2]
            assert "Analyze this" in args[0][0][2]

    def test_rejects_empty_prompt(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            HermesAgentRunner(backend="cli").run("   ")

    def test_raises_on_nonzero_exit(self) -> None:
        with patch("src.integrations.hermes_runner.shutil.which", return_value="/hermes"), \
             patch("src.integrations.hermes_runner.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="exit failure"
            )

            with pytest.raises(HermesError, match="exited with code 1"):
                HermesAgentRunner(backend="cli").run("test")

    def test_raises_on_timeout(self) -> None:
        with patch("src.integrations.hermes_runner.shutil.which", return_value="/hermes"), \
             patch("src.integrations.hermes_runner.subprocess.run", side_effect=subprocess.TimeoutExpired("hermes", 120)):
            with pytest.raises(HermesError, match="timed out"):
                HermesAgentRunner(backend="cli").run("test")

    def test_raises_on_empty_response(self) -> None:
        with patch("src.integrations.hermes_runner.shutil.which", return_value="/hermes"), \
             patch("src.integrations.hermes_runner.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(
                returncode=0,
                stdout="",
                stderr=""
            )

            with pytest.raises(HermesError, match="empty response"):
                HermesAgentRunner(backend="cli").run("test")

    def test_detects_missing_executable(self) -> None:
        with patch("src.integrations.hermes_runner.shutil.which", return_value=None):
            with pytest.raises(HermesError, match="was not found"):
                HermesAgentRunner(backend="cli")


class TestHermesAgentRunnerPython:
    """Tests for the Python backend."""

    def test_uses_python_backend_when_configured(self) -> None:
        with patch("src.integrations.hermes_runner.run_hermes_python", return_value="python response"):
            runner = HermesAgentRunner(timeout=120, backend="python")
            response = runner.run("test prompt", system_prompt="system prompt")

        assert response == "python response"

    def test_python_backend_rejects_empty_prompt(self) -> None:
        runner = HermesAgentRunner(backend="python")
        with pytest.raises(ValueError, match="cannot be empty"):
            runner.run("   ")

    def test_python_backend_wraps_python_error(self) -> None:
        with patch("src.integrations.hermes_runner.run_hermes_python",
                   side_effect=HermesPythonError("worker failed")):
            runner = HermesAgentRunner(backend="python")
            with pytest.raises(HermesError, match="worker failed"):
                runner.run("test")

    def test_python_backend_wraps_runtime_error(self) -> None:
        with patch("src.integrations.hermes_runner.run_hermes_python",
                   side_effect=RuntimeError("timeout")):
            runner = HermesAgentRunner(backend="python")
            with pytest.raises(HermesError, match="timeout"):
                runner.run("test")

    def test_python_backend_uses_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("HERMES_BACKEND", "python")
        with patch("src.integrations.hermes_runner.run_hermes_python", return_value="env response"):
            runner = HermesAgentRunner()
            response = runner.run("test")

        assert response == "env response"


class TestHermesAgentRunnerIntegration:
    """Integration tests that use the real backend.

    The CLI test is always expected to fail because Hermes CLI is blocked by
    Windows Application Control (WinError 4551). This is an environment
    restriction, not a code bug.

    The Python smoke test is a live test that hits the OpenRouter API. It
    should be run with: pytest -m live tests/unit/test_hermes_runner.py
    It will be skipped in normal runs (pytest -q).
    """

    @pytest.mark.xfail(
        reason="Hermes CLI blocked by Windows Application Control (WinError 4551)",
        strict=False
    )
    def test_actual_cli_works(self) -> None:
        """Diagnostic: real CLI call.

        This test documents the WinError 4551 blocker.
        It is expected to fail in this environment.
        """
        runner = HermesAgentRunner(timeout=60, backend="cli")
        result = runner.run("Reply with exactly: HERMES PYTHON TEST OK")
        assert result == "HERMES PYTHON TEST OK"

    @pytest.mark.live
    def test_python_backend_smoke(self) -> None:
        """Real smoke test using the Python backend.

        This test hits the OpenRouter API via the managed Hermes Python
        interpreter. It is excluded from normal runs; use:
        pytest -m live tests/unit/test_hermes_runner.py
        """
        runner = HermesAgentRunner(timeout=60, backend="python")
        result = runner.run("Reply with exactly: HERMES RUNNER PYTHON BACKEND OK")
        assert result == "HERMES RUNNER PYTHON BACKEND OK"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])