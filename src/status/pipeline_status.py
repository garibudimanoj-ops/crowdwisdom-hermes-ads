from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path("outputs/run_manifest.json")
STATUS_ARTIFACT_PATH = Path("outputs/pipeline_status.json")

REQUIRED_STAGES = [
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


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PipelineStatusError(f"Manifest not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise PipelineStatusError(f"Manifest is not valid JSON: {exc}") from exc


def _redact_secrets(data: Any) -> Any:
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            lower_key = key.lower()
            if any(
                secret in lower_key
                for secret in ("api_key", "token", "password", "secret", "credential")
            ):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, (dict, list)):
                redacted[key] = _redact_secrets(value)
            else:
                redacted[key] = value
        return redacted
    if isinstance(data, list):
        return [_redact_secrets(item) for item in data]
    return data


def _stage_to_dict(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": stage.get("stage"),
        "status": stage.get("status"),
        "started_at": stage.get("started_at"),
        "completed_at": stage.get("completed_at"),
        "outputs": stage.get("outputs") or {},
        "error": stage.get("error"),
    }


def read_pipeline_status(manifest_path: Path | None = None) -> dict[str, Any]:
    """Read the current pipeline status from the run manifest.

    Args:
        manifest_path: Path to run_manifest.json (default: outputs/run_manifest.json).

    Returns:
        Machine-readable pipeline status dict suitable for Kanban/UI consumption.
    """
    manifest_path = manifest_path or MANIFEST_PATH
    manifest = _load_manifest(manifest_path)

    stages = manifest.get("stages", [])
    stage_map = {s.get("stage"): s for s in stages}

    all_stages = []
    for name in REQUIRED_STAGES:
        if name in stage_map:
            all_stages.append(_stage_to_dict(stage_map[name]))
        else:
            all_stages.append({
                "name": name,
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "outputs": {},
                "error": None,
            })

    overall = manifest.get("overall_status", "pending")
    execution_mode = manifest.get("execution_mode", "live")

    result = {
        "execution_mode": execution_mode,
        "overall_status": overall,
        "stages": all_stages,
        "started_at": manifest.get("started_at"),
        "completed_at": manifest.get("completed_at"),
        "errors": manifest.get("errors", {}),
        "blockers": manifest.get("blockers", []),
    }

    return _redact_secrets(result)


def write_pipeline_status(
    status: dict[str, Any] | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Write pipeline status to a JSON artifact for Kanban/UI consumption.

    Args:
        status: Pre-built status dict (will call read_pipeline_status if None).
        output_path: Destination path (default: outputs/pipeline_status.json).

    Returns:
        The status dict that was written.
    """
    output_path = output_path or STATUS_ARTIFACT_PATH
    if status is None:
        status = read_pipeline_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

    return status


def get_pipeline_status(manifest_path: Path | None = None) -> dict[str, Any]:
    """Get pipeline status, reading manifest and writing status artifact.

    This is the primary public API for the Kanban/status adapter.

    Args:
        manifest_path: Optional path to run_manifest.json.

    Returns:
        Status dict with all stages, overall status, execution mode.
    """
    status = read_pipeline_status(manifest_path)
    write_pipeline_status(status)
    return status


class PipelineStatusError(Exception):
    pass
