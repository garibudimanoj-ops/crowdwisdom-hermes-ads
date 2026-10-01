from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from src.agents.video_agent import VideoAgentError


QUALITY_REPORT_PATH = Path("outputs/videos/quality_report.json")
VIDEO_OUTPUT_PATH = Path("outputs/videos/final_ad.mp4")


def _validate_file_exists(path: Path, name: str) -> tuple[bool, str]:
    if not path.exists():
        return False, f"{name} not found: {path}"
    if path.stat().st_size == 0:
        return False, f"{name} is empty: {path}"
    return True, f"{name} exists ({path.stat().st_size} bytes)"


def _run_ffprobe(path: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise VideoAgentError("ffprobe not found on PATH — FFmpeg is required") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise VideoAgentError(f"ffprobe failed: {stderr}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VideoAgentError(f"Malformed ffprobe output: {exc}") from exc


def _validate_video_quality(probe: dict[str, Any], path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    streams = probe.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not video_streams:
        errors.append("No video stream found")
    else:
        video = video_streams[0]
        codec = video.get("codec_name")
        if not codec:
            errors.append("Video codec not readable")
        width = video.get("width")
        height = video.get("height")
        if not (width and height):
            errors.append("Video resolution not readable")
        fps = video.get("r_frame_rate") or video.get("avg_frame_rate")
        if fps:
            try:
                num, den = fps.split("/")
                fps_val = int(num) / int(den)
                if fps_val < 1:
                    warnings.append(f"Low frame rate: {fps_val}fps")
            except Exception:
                warnings.append(f"Frame rate unreadable: {fps}")

    if not audio_streams:
        warnings.append("No audio stream found (video may be silent)")

    duration = probe.get("format", {}).get("duration")
    if duration:
        try:
            duration_val = float(duration)
            if duration_val < 30:
                errors.append(f"Duration too short: {duration_val:.2f}s (expected 30-60s)")
            elif duration_val > 60:
                errors.append(f"Duration too long: {duration_val:.2f}s (expected 30-60s)")
        except (ValueError, TypeError):
            warnings.append("Duration unreadable")

    return errors, warnings


def run_quality_agent(
    video_path: Path | None = None,
    mode: str = "live",
) -> dict[str, Any]:
    """Validate video quality and consistency with pipeline artifacts.

    Args:
        video_path: Path to final_ad.mp4 (default: outputs/videos/final_ad.mp4).
        mode: 'live' or 'dry_run'.

    Returns:
        dict with status, outputs, mode, and any error details.
    """
    video_path = video_path or VIDEO_OUTPUT_PATH
    mode = mode or os.environ.get("PIPELINE_MODE", "live")

    if mode == "dry_run":
        return {
            "status": "completed",
            "outputs": {
                "quality_report_json": str(QUALITY_REPORT_PATH),
                "note": "dry_run: quality validation skipped",
            },
            "mode": "dry_run",
        }

    quality_report: dict[str, Any] = {
        "status": "PASS",
        "errors": [],
        "warnings": [],
        "checks": {},
        "metadata": {},
    }

    try:
        exists, exists_msg = _validate_file_exists(video_path, "Video file")
        if not exists:
            raise VideoAgentError(exists_msg)
        quality_report["checks"]["file_exists"] = True

        probe = _run_ffprobe(video_path)
        quality_report["metadata"] = {
            "format": probe.get("format", {}).get("format_name"),
            "size": probe.get("format", {}).get("size"),
            "duration": probe.get("format", {}).get("duration"),
        }
        quality_report["checks"]["ffprobe_success"] = True

        errors, warnings = _validate_video_quality(probe, video_path)
        quality_report["errors"].extend(errors)
        quality_report["warnings"].extend(warnings)

        if errors:
            quality_report["status"] = "FAIL"
        elif warnings:
            quality_report["status"] = "WARNING"

        QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with QUALITY_REPORT_PATH.open("w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2, ensure_ascii=False)

        return {
            "status": quality_report["status"].lower(),
            "outputs": {
                "quality_report_json": str(QUALITY_REPORT_PATH),
                "video_metadata": quality_report["metadata"],
            },
            "mode": "live",
            "errors": quality_report["errors"],
            "warnings": quality_report["warnings"],
        }
    except VideoAgentError:
        raise
    except Exception as exc:
        raise VideoAgentError(f"Quality validation failed: {exc}") from exc
