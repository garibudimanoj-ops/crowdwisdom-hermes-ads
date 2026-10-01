"""Hermes Python backend worker.

Executed by the managed Hermes Python 3.11 interpreter.
Reads a JSON request from stdin, runs AIAgent.run_conversation,
and writes a single JSON object to stdout.

Input (stdin):
{"prompt": "...", "system_prompt": "..." or null}

Success output (stdout):
{"ok": true, "response": "..."}

Error output (stdout):
{"ok": false, "error": "..."}

All Hermes diagnostic/log output goes to stderr.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

HERMES_RUN_AGENT_DIR = str(
    Path(r"C:\Users\garib\AppData\Local\hermes\hermes-agent")
)
HERMES_BASE_URL = "https://openrouter.ai/api/v1"
HERMES_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

SAFE_ERRORS = {
    1: "Managed Python startup error",
    2: "Failed to import Hermes AIAgent",
    3: "Invalid input request",
    4: "Hermes conversation failed",
    5: "Worker processing error",
}


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        _emit_error(2, "Invalid JSON input")
        return

    prompt = data.get("prompt")
    system_prompt = data.get("system_prompt")

    if not isinstance(prompt, str) or not prompt.strip():
        _emit_error(3, "Prompt must be a non-empty string")
        return

    if system_prompt is not None and not isinstance(system_prompt, str):
        _emit_error(3, "System prompt must be a string or null")
        return

    try:
        sys.path.insert(0, HERMES_RUN_AGENT_DIR)

        with contextlib.redirect_stdout(sys.stderr):
            from run_agent import AIAgent

            agent = AIAgent(
                base_url=HERMES_BASE_URL,
                model=HERMES_MODEL,
                max_tokens=16384,
            )
            result = agent.run_conversation(
                prompt,
                system_message=system_prompt,
            )
    except Exception:
        _emit_error(4, "AIAgent request failed")
        return

    if not isinstance(result, dict):
        _emit_error(5, "Invalid AIAgent response")
        return

    # Check if the conversation actually succeeded
    if result.get("failed", True) or not result.get("completed", False):
        _emit_error(4, "Hermes conversation failed", result)
        return

    final_response = result.get("final_response")

    if not isinstance(final_response, str) or not final_response:
        _emit_error(5, "Empty final_response from AIAgent")
        return

    _emit_ok(final_response)


def _classify_failure(result: dict) -> dict:
    """Classify Hermes failure into a safe, machine-readable error.

    Returns dict with: failure_kind, http_status (optional)
    """
    # Extract safe diagnostic fields
    error = result.get("error", "")
    failure_reason = result.get("failure_reason", "")
    failure_retryable = result.get("failure_retryable", False)
    turn_exit_reason = result.get("turn_exit_reason", "")
    model = result.get("model", "")
    requested_model = result.get("requested_model", "")
    provider = result.get("provider", "")

    # Combine all error text for classification
    error_text = " ".join([
        str(error),
        str(failure_reason),
        str(turn_exit_reason),
    ]).lower()

    # Rate limiting (429, quota, rate limit)
    if any(kw in error_text for kw in ["429", "rate limit", "quota", "too many requests"]):
        return {"failure_kind": "rate_limited", "http_status": 429}

    # Authentication failure (401, 403, auth, unauthorized, invalid key)
    if any(kw in error_text for kw in ["401", "403", "authentication", "unauthorized", "invalid key", "invalid token"]):
        return {"failure_kind": "authentication_failed", "http_status": 401}

    # Invalid request (400, bad request, invalid request)
    if any(kw in error_text for kw in ["400", "bad request", "invalid request"]):
        return {"failure_kind": "invalid_request", "http_status": 400}

    # Timeout
    if any(kw in error_text for kw in ["timeout", "timed out"]):
        return {"failure_kind": "timeout", "http_status": 408}

    # Provider error (5xx, provider error, internal error)
    if any(kw in error_text for kw in ["500", "502", "503", "504", "provider error", "internal error"]):
        return {"failure_kind": "provider_error", "http_status": 500}

    return {"failure_kind": "unknown", "http_status": None}


def _emit_ok(response: str) -> None:
    json.dump({"ok": True, "response": response}, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _emit_error(code: int, message: str, result: dict | None = None) -> None:
    error_data = {"ok": False, "error": message, "code": code}
    if result is not None:
        # Extract Hermes failure diagnostics
        if isinstance(result, dict):
            hermes_fields = {}
            for field in ["failed", "completed", "error", "failure_reason", 
                         "failure_retryable", "turn_exit_reason", "model",
                         "requested_model", "provider"]:
                if field in result:
                    hermes_fields[field] = result[field]
            if hermes_fields:
                error_data["hermes_result"] = hermes_fields

        # Add safe failure classification
        classification = _classify_failure(result)
        error_data.update(classification)
    
    json.dump(error_data, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
