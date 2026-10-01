from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_BASE_URL = "https://api.pexels.com/v1"

# Pexels video search parameters

class PexelsVideoClientError(Exception):
    """Raised when Pexels API operations fail."""


def _require_api_key() -> str:
    """Return the Pexels API key or raise a clear error."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise PexelsVideoClientError(
            "PEXELS_API_KEY environment variable not set. "
            "Place it in .env or export before running."
        )
    return key


def _get_headers() -> Dict[str, str]:
    """Return headers for Pexels API requests."""
    return {"Authorization": f"{PEXELS_API_KEY}"}


def search_videos(
    query: str,
    orientation: str = "vertical",
    page: int = 1,
    per_page: int = 15,
    min_duration: int = 1,
    max_duration: int = 300,
    size: str = "large",
    sort: str = "relevant",
    color: Optional[str] = None,
) -> Dict[str, Any]:
    """Search Pexels videos and return structured results.

    Args:
        query: Search query (e.g., "trader eyes monitors")
        orientation: Video orientation (vertical, horizontal, square)
        page: Page number for pagination
        per_page: Number of results per page (max 15)
        min_duration: Minimum video duration in seconds
        max_duration: Maximum video duration in seconds
        size: Video quality/size (small, medium, large)
        sort: Sorting method (relevant, newest, popular)
        color: Filter by color (optional)

    Returns:
        Dict containing search response from Pexels API

    Raises:
        PexelsVideoClientError: On network errors or API failures
    """
    if not PEXELS_API_KEY:
        raise PexelsVideoClientError("API key not configured")

    search_params = {
        "query": query,
        "orientation": orientation,
        "page": page,
        "per_page": per_page,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "size": size,
        "sort": sort,
    }
    if color:
        search_params["color"] = color

    try:
        response = requests.get(
            f"{PEXELS_BASE_URL}/search/videos",
            headers=_get_headers(),
            params=search_params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise PexelsVideoClientError(f"Pexels API request failed: {e}")


def get_video_details(video_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific video.

    Args:
        video_id: The Pexels video ID

    Returns:
        Video details from Pexels API

    Raises:
        PexelsVideoClientError: On API failures
    """
    if not PEXELS_API_KEY:
        raise PexelsVideoClientError("API key not configured")

    try:
        response = requests.get(
            f"{PEXELS_BASE_URL}/videos/{video_id}",
            headers=_get_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise PexelsVideoClientError(f"Failed to get video details: {e}")


def normalize_video_response(raw_video: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Normalize Pexels video API response into standardized structure.

    Args:
        raw_video: Raw video data from Pexels API
        query: The search query used

    Returns:
        Normalized video data with consistent field names
    """
    video_files = raw_video.get("video_files", [])

    normalized_files = []
    for file_info in video_files:
        if file_info.get("quality") == "hd" and file_info.get("width", 0) >= 720:
            normalized_files.append(
                {
                    "quality": file_info.get("quality", ""),
                    "file_type": file_info.get("file_type", ""),
                    "width": file_info.get("width", 0),
                    "height": file_info.get("height", 0),
                    "duration": file_info.get("duration", 0),
                    "link": file_info.get("link", ""),
                }
            )

    return {
        "asset_id": raw_video.get("id", ""),
        "source": "Pexels",
        "source_url": raw_video.get("url", ""),
        "creator": raw_video.get("user", {}).get("name", "Unknown"),
        "creator_url": raw_video.get("user", {}).get("url", ""),
        "width": raw_video.get("width", 0),
        "height": raw_video.get("height", 0),
        "duration": raw_video.get("duration", 0),
        "video_files": normalized_files,
        "thumbnail": raw_video.get("image", ""),
        "frame_rate": raw_video.get("frame_rate", 0),
        "tags": raw_video.get("tags", []),
        "categories": raw_video.get("categories", []),
        "video_snippet": raw_video.get("video_snippet", ""),
        "query": query,
        "fetched_at": raw_video.get("fetched_at"),
    }


def extract_best_video_file(video: Dict[str, Any]) -> Dict[str, Any]:
    """Select the best video file from a normalized video entry.

    Args:
        video: Normalized video data

    Returns:
        The best video file entry
    """
    video_files = video.get("video_files", [])
    if not video_files:
        return {
            "quality": "",
            "file_type": "",
            "width": 0,
            "height": 0,
            "duration": 0,
            "link": "",
        }

    hd_files = [f for f in video_files if f.get("quality") == "hd" and f.get("width", 0) >= 720]
    if hd_files:
        return max(hd_files, key=lambda f: f.get("width", 0) * f.get("height", 0))

    return video_files[0]


def filter_vertical_videos(videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter videos to only include vertical orientation.

    Args:
        videos: List of normalized video data

    Returns:
        Only videos with height > width (vertical)
    """
    return [v for v in videos if v.get("height", 0) > v.get("width", 0)]


def filter_crop_friendly_videos(videos: List[Dict[str, Any]], target_width: int = 1080, target_height: int = 1920) -> List[Dict[str, Any]]:
    """Filter videos that can be cropped to target aspect ratio without quality loss.

    Args:
        videos: List of normalized video data
        target_width: Target width (e.g., 1080 for 9:16)
        target_height: Target height (e.g., 1920 for 9:16)

    Returns:
        Videos suitable for 9:16 aspect ratio after cropping
    """
    result = []
    for video in videos:
        video_w = video.get("width", 0)
        video_h = video.get("height", 0)
        video_duration = video.get("duration", 0)

        if video_w <= 0 or video_h <= 0:
            continue

        video_aspect = video_w / video_h
        target_aspect = target_width / target_height

        if abs(video_aspect - target_aspect) < 0.1:
            if video_duration >= 6 and video_duration <= 12:
                result.append(video)

    return result


# Environment and testing helpers


class PexelsTestUtils:
    """Utility class for testing Pexels client functions."""

    @staticmethod
    def mock_api_response(search_query: str, video_count: int = 5) -> Dict[str, Any]:
        """Generate a realistic mock Pexels API response for testing."""
        videos = []
        for i in range(video_count):
            video = {
                "id": f"test_video_{i}",
                "url": f"https://www.pexels.com/video/test-video-{i}",
                "width": 1080 if i % 3 == 0 else 1920,
                "height": 1920 if i % 3 == 0 else 1080,
                "duration": 8 + i * 2,
                "frame_rate": 30,
                "video_files": [
                    {
                        "quality": "hd",
                        "file_type": "mp4",
                        "width": 1080 if i % 3 == 0 else 1920,
                        "height": 1920 if i % 3 == 0 else 1080,
                        "duration": 8 + i * 2,
                        "link": f"https://videos.pexels.com/files/{i}/test_video_{i}.mp4",
                    }
                ],
                "image": f"https://images.pexels.com/photos/{i}/preview.jpg",
                "tags": ["trader", "eyes", "monitors"] if i % 2 == 0 else ["workspace", "screen"],
                "categories": ["business"],
                "user": {
                    "name": f"Test Creator {i}",
                    "url": f"https://www.pexels.com/@testcreator{i}",
                },
                "video_snippet": f"Test video snippet {i}",
                "fetched_at": "2026-09-27T07:17:16Z",
            }
            videos.append(video)

        return {
            "total_results": video_count * 10,
            "page": 1,
            "per_page": video_count,
            "url": f"https://www.pexels.com/search/{quote(search_query)}?page=1",
            "videos": videos,
        }

    @staticmethod
    def mock_empty_response() -> Dict[str, Any]:
        """Generate a mock empty Pexels API response."""
        return {
            "total_results": 0,
            "page": 1,
            "per_page": 15,
            "url": "https://www.pexels.com/search/test",
            "videos": [],
        }

    @staticmethod
    def mock_error_response(status_code: int = 500, error_message: str = "Internal Server Error") -> Dict[str, Any]:
        """Generate a mock error response from Pexels API."""
        return {
            "error": status_code,
            "message": error_message,
            "type": "error",
        }

    @staticmethod
    def simulate_timeout_error() -> requests.RequestException:
        """Simulate a network timeout error."""
        return requests.exceptions.Timeout("Request timed out")

    @staticmethod
    def simulate_auth_error() -> requests.RequestException:
        """Simulate an authentication error."""
        return requests.exceptions.HTTPError("401 Client Error: Unauthorized")


if __name__ == "__main__":
    print("Pexels Video Client - Module loaded successfully")
    print(f"Default API base URL: {PEXELS_BASE_URL}")
    print(f"API key configured: {'Yes' if PEXELS_API_KEY else 'No'}")
