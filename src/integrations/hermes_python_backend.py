"""Hermes Python backend - invokes managed Hermes Python interpreter.

Architecture:
- Project Python 3.13 remains the main runtime.
- Managed Hermes Python 3.11 remains isolated.
- The parent launches the static worker file: hermes_python_worker.py
- The worker reads JSON from stdin, runs AIAgent.run_conversation,
  and writes a single JSON object to stdout.

All Hermes diagnostic/log output goes to stderr inside the worker.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class HermesPythonError(RuntimeError):
    """Raised when the Hermes Python backend fails."""

    def __init__(self, message: str, failure_kind: str | None = None, http_status: int | None = None):
        super().__init__(message)
        self.failure_kind = failure_kind
        self.http_status = http_status


# Paths to the managed Hermes environment
HERMES_HOME = Path(r"C:\Users\garib\AppData\Local\hermes")
HERMES_MANAGED_PYTHON = HERMES_HOME / "hermes-agent" / "venv" / "Scripts" / "python.exe"
HERMES_RUN_AGENT_DIR = HERMES_HOME / "hermes-agent"

# Confirmed Hermes configuration (from config.yaml)
HERMES_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
HERMES_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class HermesPythonConfig:
    """Configuration for the Python backend."""

    model: str = HERMES_MODEL
    base_url: str = HERMES_BASE_URL
    timeout: int = 300
    managed_python: str = str(HERMES_MANAGED_PYTHON)
    worker_script: str = str(
        Path(__file__).resolve().parent / "hermes_python_worker.py"
    )

    @classmethod
    def from_env(cls) -> HermesPythonConfig:
        """Load configuration from environment variables."""
        return cls(
            model=os.environ.get("HERMES_MODEL", HERMES_MODEL),
            base_url=os.environ.get("HERMES_BASE_URL", HERMES_BASE_URL),
            timeout=int(os.environ.get("HERMES_TIMEOUT", "300")),
        )


def _safe_error_message(exc: Exception) -> str:
    """Return a safe, non-secret error message."""
    return "Hermes Python backend request failed"


def run_hermes_python(
    prompt: str,
    system_prompt: str | None = None,
    config: HermesPythonConfig | None = None,
) -> str:
    """
    Run a prompt through Hermes Python backend.

    Returns the final_response text from AIAgent.run_conversation.
    """
    if config is None:
        config = HermesPythonConfig.from_env()

    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    # Validate managed Python exists
    if not Path(config.managed_python).exists():
        raise RuntimeError(
            f"Managed Hermes Python not found at: {config.managed_python}. "
            "Ensure Hermes is installed and the venv exists."
        )

    # Validate worker script exists
    if not Path(config.worker_script).exists():
        raise RuntimeError(
            f"Hermes Python worker script not found at: {config.worker_script}."
        )

    # Build JSON request payload
    request_payload = {
        "prompt": prompt.strip(),
        "system_prompt": system_prompt.strip() if system_prompt else None,
    }
    request_json = json.dumps(request_payload)

    try:
        result = subprocess.run(
            [config.managed_python, config.worker_script],
            input=request_json,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=config.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Hermes Python backend timed out after {config.timeout} seconds."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Failed to start managed Python: {exc}"
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Hermes Python worker exited with code {result.returncode}."
        )

    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError("Hermes Python worker returned empty output.")

    # Parse exactly one JSON object
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse worker output as JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Worker output is not a JSON object.")

    if not parsed.get("ok"):
        error = parsed.get("error", "Unknown worker error")
        failure_kind = parsed.get("failure_kind", "unknown")
        http_status = parsed.get("http_status")
        message = f"Hermes Python backend failed: {failure_kind}"
        if http_status:
            message += f" (HTTP {http_status})"
        raise HermesPythonError(message, failure_kind, http_status)

    response = parsed.get("response", "")
    if not isinstance(response, str) or not response:
        raise RuntimeError("Hermes Python backend returned empty response.")

    return response


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hermes Python backend test")
    parser.add_argument("prompt", help="Prompt to send")
    parser.add_argument("--system", help="System prompt", default=None)
    args = parser.parse_args()

    response = run_hermes_python(args.prompt, args.system)
    print(response)