from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


VIDEO_OUTPUT_PATH = Path("outputs/videos/final_ad.mp4")
STORYBOARD_PATH = Path("outputs/storyboards/final_storyboard.json")
OPMONTAGE_COMPOSER_DIR = Path(r"C:\AI Projects\OpenMontage\remotion-composer")
DEFAULT_THEME = "flat-motion-graphics"


class VideoAgentError(Exception):
    pass


def _load_storyboard(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise VideoAgentError(f"Storyboard not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise VideoAgentError(f"Invalid JSON in storyboard: {exc}") from exc
    if not isinstance(data, dict):
        raise VideoAgentError("Storyboard must be a JSON object")
    return data


def _convert_storyboard_to_props(storyboard: dict[str, Any]) -> dict[str, Any]:
    scenes = storyboard.get("scenes", [])
    if not scenes:
        raise VideoAgentError("Storyboard has no scenes")

    cuts: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []

    def _convert_dimensions(width: int | None, height: int | None) -> tuple[int, int]:
        """Convert landscape dimensions to portrait 1080x1920.
        
        If input is landscape (width > height), swap to portrait.
        If input is portrait or square, keep as-is but ensure minimum 1080x1920.
        If no dimensions provided, default to 1080x1920.
        """
        if width is None or height is None:
            return (1080, 1920)
        
        # If landscape (w > h), swap to portrait
        if width > height:
            return (height, width)
        
        # Portrait or square - keep aspect but ensure minimum portrait
        return (width, height)

    for idx, scene in enumerate(scenes):
        cut_id = scene.get("id") or f"scene-{idx}"
        scene_type = scene.get("type", "text_card")
        start = scene.get("start_seconds", idx * 5)
        end = scene.get("end_seconds", (idx + 1) * 5)

        # Convert dimensions if provided
        scene_width = scene.get("width")
        scene_height = scene.get("height")
        conv_width, conv_height = _convert_dimensions(scene_width, scene_height)

        cut: dict[str, Any] = {
            "id": cut_id,
            "source": scene.get("source", ""),
            "type": scene_type,
            "in_seconds": start,
            "out_seconds": end,
            "width": conv_width,
            "height": conv_height,
        }

        if scene_type in ("text_card", "hero_title", "section_title"):
            cut["text"] = scene.get("text", "")
            cut["subtitle"] = scene.get("subtitle", "")
            cut["backgroundColor"] = scene.get("background_color", "#0F172A")
            cut["color"] = scene.get("text_color", "#F8FAFC")
        elif scene_type == "stat_card":
            cut["stat"] = scene.get("stat", "")
            cut["subtitle"] = scene.get("subtitle", "")
            cut["accentColor"] = scene.get("accent_color", "#22D3EE")
            cut["backgroundColor"] = scene.get("background_color", "#0F172A")
        elif scene_type in ("bar_chart", "line_chart", "pie_chart"):
            cut["title"] = scene.get("title", "")
            cut["chartData"] = scene.get("data", [])
            cut["chartColors"] = scene.get("colors", ["#22D3EE", "#A78BFA", "#F59E0B", "#34D399"])
            cut["backgroundColor"] = scene.get("background_color", "#0F172A")
            cut["showGrid"] = scene.get("show_grid", True)
            cut["showValues"] = scene.get("show_values", True)
        elif scene_type == "comparison":
            cut["title"] = scene.get("title", "")
            cut["left"] = scene.get("left", "")
            cut["right"] = scene.get("right", "")
            cut["backgroundColor"] = scene.get("background_color", "#0F172A")
        elif scene_type == "callout":
            cut["text"] = scene.get("text", "")
            cut["backgroundColor"] = scene.get("background_color", "#0F172A")
            cut["accentColor"] = scene.get("accent_color", "#F59E0B")

        if scene.get("overlay"):
            overlays.append({
                "type": scene.get("overlay_type", "section_title"),
                "in_seconds": start,
                "out_seconds": end,
                "text": scene.get("overlay", ""),
                "subtitle": scene.get("overlay_subtitle", ""),
                "accentColor": scene.get("accent_color", "#22D3EE"),
                "position": scene.get("overlay_position", "bottom-right"),
            })

        cuts.append(cut)

    return {
        "theme": DEFAULT_THEME,
        "cuts": cuts,
        "overlays": overlays,
        "captions": [],
        "audio": {},
    }


def _render(
    props: dict[str, Any],
    output_path: Path,
    composer_dir: Path,
) -> subprocess.CompletedProcess[bytes]:
    if not (composer_dir / "src" / "index.tsx").exists():
        raise VideoAgentError(f"OpenMontage composer not found at {composer_dir}")

    # Use local Remotion CLI from the composer directory
    # Try different possible locations for the local CLI
    local_cli_cmd = None
    
    # Windows: .cmd file in node_modules/.bin
    windows_cli = composer_dir / "node_modules" / ".bin" / "remotion.cmd"
    if windows_cli.exists():
        local_cli_cmd = str(windows_cli)
    # Unix/Linux/macOS: executable file in node_modules/.bin
    else:
        unix_cli = composer_dir / "node_modules" / ".bin" / "remotion"
        if unix_cli.exists():
            local_cli_cmd = str(unix_cli)
    
    if not local_cli_cmd:
        raise VideoAgentError(f"Local Remotion CLI not found in {composer_dir}/node_modules/.bin")

    output_path = output_path.resolve()
    props_path = (output_path.parent / "_props.json").resolve()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with props_path.open("w", encoding="utf-8") as fh:
        json.dump(props, fh, indent=2, ensure_ascii=False)

    # Get timeout from environment variable, default to 600 seconds (10 minutes)
    # Use a safe parse that falls back to the default on any non-integer value
    try:
        timeout = int(os.environ.get("VIDEO_RENDER_TIMEOUT", "600"))
    except (ValueError, TypeError):
        timeout = 600

    try:
        result = subprocess.run(
            [
                local_cli_cmd,
                "render",
                "src/index.tsx",
                "CinematicStoryboard",
                str(output_path),
                f"--props={props_path}",
                "--width=1080",
                "--height=1920",
                "--codec",
                "h264",
            ],
            cwd=composer_dir,
            capture_output=True,
            timeout=timeout,
        )
    finally:
        if props_path.exists():
            props_path.unlink()

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise VideoAgentError(f"OpenMontage render failed: {stderr}")

    return result


def run_video_agent(
    storyboard_path: Path | None = None,
    output_path: Path | None = None,
    mode: str = "live",
    composer_dir: Path = OPMONTAGE_COMPOSER_DIR,
) -> dict[str, Any]:
    """Render a video from the pipeline storyboard using OpenMontage.

    Args:
        storyboard_path: Path to final_storyboard.json (default: outputs/storyboards/final_storyboard.json).
        output_path: Target MP4 path (default: outputs/videos/final_ad.mp4).
        mode: 'live' or 'dry_run'. In dry_run, no OpenMontage process is started.
        composer_dir: OpenMontage remotion-composer directory.

    Returns:
        dict with status, outputs, mode, and any error details.
    """
    storyboard_path = storyboard_path or STORYBOARD_PATH
    output_path = output_path or VIDEO_OUTPUT_PATH
    mode = mode or os.environ.get("PIPELINE_MODE", "live")

    if mode == "dry_run":
        return {
            "status": "completed",
            "outputs": {
                "video_mp4": str(output_path),
                "note": "dry_run: video render skipped",
            },
            "mode": "dry_run",
        }

    try:
        storyboard = _load_storyboard(storyboard_path)
        props = _convert_storyboard_to_props(storyboard)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _render(props, output_path, composer_dir)

        if not output_path.exists():
            raise VideoAgentError(f"Render completed but output file was not created: {output_path}")

        return {
            "status": "completed",
            "outputs": {"video_mp4": str(output_path)},
            "mode": "live",
        }
    except VideoAgentError:
        raise
    except Exception as exc:
        raise VideoAgentError(f"Video render failed: {exc}") from exc