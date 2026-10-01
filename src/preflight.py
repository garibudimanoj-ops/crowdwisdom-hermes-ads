from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Project root (this file lives at src/preflight.py, so root is two levels up)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env safely
load_dotenv(PROJECT_ROOT / ".env")

# Required environment variables (names only — never print values)
REQUIRED_ENV_VARS = [
    "OPENROUTER_API_KEY",
    "APIFY_API_TOKEN",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
    "OPENROUTER_MODEL",
    "OPENMONTAGE_PATH",
    "CROWDWISDOM_URL",
]

# Secret variable names (never print values)
SECRET_ENV_VARS = {
    "OPENROUTER_API_KEY",
    "APIFY_API_TOKEN",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
}

# Required Python modules to import
REQUIRED_PYTHON_MODULES = [
    "pydantic",
    "apify_client",
    "fastapi",
    "tenacity",
    "dotenv",
    "pytest",
]

# Required output directories (must exist or can be created)
REQUIRED_OUTPUT_DIRS = [
    "outputs/ads",
    "outputs/insights",
    "outputs/research",
    "outputs/scripts",
    "outputs/creative_review",
    "outputs/storyboards",
    "outputs/videos",
    "outputs/logs",
    "data/processed",
]

# Pre-existing artifacts required before live run
REQUIRED_ARTIFACTS = [
    "outputs/ads/ads.json",
    "outputs/insights/marketing_insights.json",
    "outputs/research/research.json",
]


class PreflightError(Exception):
    pass


def _check_env_file() -> dict[str, Any]:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        return {
            "name": "env_file",
            "status": "pass",
            "detail": ".env exists",
        }
    return {
        "name": "env_file",
        "status": "warning",
        "detail": ".env not found — using system environment variables directly",
        "suggestion": "create .env file with required environment variables",
    }


def _check_env_var(name: str) -> dict[str, Any]:
    value = os.environ.get(name)
    if value:
        return {
            "name": f"env:{name}",
            "status": "pass",
            "detail": f"{name} is present",
        }
    return {
        "name": f"env:{name}",
        "status": "fail",
        "detail": f"{name} is missing",
    }


def _check_python_module(module_name: str) -> dict[str, Any]:
    try:
        __import__(module_name)
        return {
            "name": f"python:{module_name}",
            "status": "pass",
            "detail": f"{module_name} importable",
        }
    except ImportError as exc:
        return {
            "name": f"python:{module_name}",
            "status": "fail",
            "detail": f"{module_name} not importable: {exc}",
        }


def _check_executable(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    if path:
        return {
            "name": f"executable:{name}",
            "status": "pass",
            "detail": f"{name} found on PATH",
        }
    return {
        "name": f"executable:{name}",
        "status": "fail",
        "detail": f"{name} not found on PATH",
    }


def _check_path_exists(name: str, path: Path) -> dict[str, Any]:
    if path.exists():
        return {
            "name": name,
            "status": "pass",
            "detail": f"{path} exists",
        }
    return {
        "name": name,
        "status": "fail",
        "detail": f"{path} does not exist",
    }


def _check_output_dir(name: str, path: Path) -> dict[str, Any]:
    if path.exists() and path.is_dir():
        return {
            "name": name,
            "status": "pass",
            "detail": f"{path} exists",
        }
    return {
        "name": name,
        "status": "warning",
        "detail": f"{path} does not exist (will be created on demand)",
        "suggestion": f"mkdir -p {path}",
    }


def _check_artifact(name: str, path: Path) -> dict[str, Any]:
    if path.exists() and path.is_file():
        return {
            "name": name,
            "status": "pass",
            "detail": f"{path} exists ({path.stat().st_size} bytes)",
        }
    return {
        "name": name,
        "status": "fail",
        "detail": f"{path} does not exist",
    }


def _check_manifest_readable() -> dict[str, Any]:
    manifest_path = PROJECT_ROOT / "outputs" / "run_manifest.json"
    if not manifest_path.exists():
        return {
            "name": "manifest_readable",
            "status": "warning",
            "detail": "run_manifest.json not found (pipeline not yet run)",
        }
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {
                "name": "manifest_readable",
                "status": "fail",
                "detail": "run_manifest.json is not a JSON object",
            }
        return {
            "name": "manifest_readable",
            "status": "pass",
            "detail": "run_manifest.json is valid JSON",
        }
    except json.JSONDecodeError as exc:
        return {
            "name": "manifest_readable",
            "status": "fail",
            "detail": f"run_manifest.json is malformed: {exc}",
        }


def _check_status_artifact_readable() -> dict[str, Any]:
    status_path = PROJECT_ROOT / "outputs" / "pipeline_status.json"
    if not status_path.exists():
        return {
            "name": "status_artifact_readable",
            "status": "warning",
            "detail": "pipeline_status.json not found (status adapter not yet run)",
        }
    try:
        with status_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {
                "name": "status_artifact_readable",
                "status": "fail",
                "detail": "pipeline_status.json is not a JSON object",
            }
        return {
            "name": "status_artifact_readable",
            "status": "pass",
            "detail": "pipeline_status.json is valid JSON",
        }
    except json.JSONDecodeError as exc:
        return {
            "name": "status_artifact_readable",
            "status": "fail",
            "detail": f"pipeline_status.json is malformed: {exc}",
        }


def _check_unique_data() -> dict[str, Any]:
    unique_data_dir = PROJECT_ROOT / "data" / "unique_data"
    if not unique_data_dir.exists():
        return {
            "name": "unique_data",
            "status": "warning",
            "detail": "data/unique_data directory does not exist",
        }
    json_files = list(unique_data_dir.glob("*.json"))
    if not json_files:
        return {
            "name": "unique_data",
            "status": "warning",
            "detail": "data/unique_data directory exists but contains no JSON files — no unique data available",
        }
    return {
        "name": "unique_data",
        "status": "pass",
        "detail": f"data/unique_data contains {len(json_files)} JSON file(s)",
    }


def _check_not_locked() -> dict[str, Any]:
    lock_path = PROJECT_ROOT / ".pipeline.lock"
    if lock_path.exists():
        return {
            "name": "not_locked",
            "status": "fail",
            "detail": "Pipeline appears to be in a locked/unfinished run",
        }
    return {
        "name": "not_locked",
        "status": "pass",
        "detail": "No lock file present",
    }


def _redact_secrets(data: Any) -> Any:
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            lower_key = key.lower()
            if any(secret in lower_key for secret in ("api_key", "token", "password", "secret", "credential")):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, (dict, list)):
                redacted[key] = _redact_secrets(value)
            else:
                redacted[key] = value
        return redacted
    if isinstance(data, list):
        return [_redact_secrets(item) for item in data]
    return data


def run_preflight() -> dict[str, Any]:
    """Run all local preflight checks and return a structured report.

    No network calls are made — only local filesystem and PATH checks.

    Returns:
        dict with 'ready' boolean, 'checks' list, and 'summary'.
    """
    checks: list[dict[str, Any]] = []

    # 1. .env file
    checks.append(_check_env_file())

    # 2. Required environment variables
    for var_name in REQUIRED_ENV_VARS:
        checks.append(_check_env_var(var_name))

    # 3. Python environment
    for module_name in REQUIRED_PYTHON_MODULES:
        checks.append(_check_python_module(module_name))

    # 4. node on PATH
    checks.append(_check_executable("node"))

    # 5. npx on PATH
    checks.append(_check_executable("npx"))

    # 6. ffprobe on PATH
    checks.append(_check_executable("ffprobe"))

    # 7. OpenMontage composer exists
    openmontage_path = os.environ.get("OPENMONTAGE_PATH", r"C:\AI Projects\OpenMontage\remotion-composer")
    composer_dir = Path(openmontage_path)
    checks.append(_check_path_exists("openmontage_composer", composer_dir))

    # 8. remotion-composer/src/index.tsx exists
    index_path = composer_dir / "src" / "index.tsx"
    checks.append(_check_path_exists("composer_index", index_path))

    # 9. remotion-composer/node_modules exists
    node_modules_path = composer_dir / "node_modules"
    checks.append(_check_path_exists("composer_node_modules", node_modules_path))

    # 10. Required output directories
    for dir_name in REQUIRED_OUTPUT_DIRS:
        dir_path = PROJECT_ROOT / dir_name
        checks.append(_check_output_dir(f"output_dir:{dir_name}", dir_path))

    # 11. Pre-existing artifacts (genuine prerequisites, not production outputs)
    for artifact_name in REQUIRED_ARTIFACTS:
        artifact_path = PROJECT_ROOT / artifact_name
        checks.append(_check_artifact(f"artifact:{artifact_name}", artifact_path))

    # 12. unique_data status
    checks.append(_check_unique_data())

    # 13. Manifest readable
    checks.append(_check_manifest_readable())

    # 14. Status artifact readable
    checks.append(_check_status_artifact_readable())

    # 15. Not locked
    checks.append(_check_not_locked())

    # Determine readiness: ready if no 'fail' checks
    failed_checks = [c for c in checks if c["status"] == "fail"]
    warning_checks = [c for c in checks if c["status"] == "warning"]
    ready = len(failed_checks) == 0

    report = {
        "ready": ready,
        "checks": _redact_secrets(checks),
        "summary": {
            "total": len(checks),
            "pass": len([c for c in checks if c["status"] == "pass"]),
            "warning": len(warning_checks),
            "fail": len(failed_checks),
        },
    }

    return report


def write_preflight_report(
    report: dict[str, Any] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Write preflight report to outputs/preflight_report.json."""
    output_path = output_path or (PROJECT_ROOT / "outputs" / "preflight_report.json")
    if report is None:
        report = run_preflight()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report
