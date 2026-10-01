"""HermesAgentRunner - wraps Hermes CLI and Python backend."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from src.integrations.hermes_python_backend import (
    HermesPythonConfig,
    HermesPythonError,
    run_hermes_python,
)


class HermesError(RuntimeError):
    """Raised when the Hermes backend cannot complete a request."""


@dataclass
class HermesAgentRunner:
    """Run prompts through Hermes CLI or Python backend."""

    timeout: int = 300
    backend: str | None = None

    def __post_init__(self) -> None:
        self.backend = (self.backend or os.environ.get("HERMES_BACKEND", "cli")).lower()
        self._python_config = HermesPythonConfig(timeout=self.timeout)

        if self.backend == "cli":
            self.executable = shutil.which("hermes")
            if not self.executable:
                raise HermesError(
                    "Hermes CLI was not found in PATH. "
                    "Run 'hermes --version' in PowerShell first."
                )
        else:
            self.executable = None

    def run(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Send a prompt to Hermes and return its text response."""
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if self.backend == "python":
            return self._run_python(prompt, system_prompt)
        return self._run_cli(prompt, system_prompt)

    def _run_cli(self, prompt: str, system_prompt: str | None) -> str:
        final_prompt = prompt.strip()

        if system_prompt and system_prompt.strip():
            final_prompt = (
                "SYSTEM INSTRUCTIONS:\n"
                f"{system_prompt.strip()}\n\n"
                "USER TASK:\n"
                f"{prompt.strip()}"
            )

        try:
            result = subprocess.run(
                [self.executable, "-z", final_prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HermesError(
                f"Hermes request timed out after {self.timeout} seconds."
            ) from exc
        except OSError as exc:
            raise HermesError(f"Failed to start Hermes: {exc}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise HermesError(
                f"Hermes exited with code {result.returncode}."
                + (f"\n{stderr}" if stderr else "")
            )

        response = result.stdout.strip()
        if not response:
            raise HermesError("Hermes returned an empty response.")

        return response

    def _run_python(self, prompt: str, system_prompt: str | None) -> str:
        try:
            return run_hermes_python(prompt, system_prompt, self._python_config)
        except HermesPythonError as exc:
            raise HermesError(str(exc)) from exc
        except RuntimeError as exc:
            raise HermesError(str(exc)) from exc