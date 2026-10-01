from __future__ import annotations

import os
from typing import Any

from tavily import TavilyClient


class TavilyToolError(RuntimeError):
    """Raised when a Tavily search operation fails."""


class TavilyTool:
    """Wrapper around Tavily API for web search."""

    def __init__(self) -> None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise TavilyToolError("TAVILY_API_KEY is missing from the environment.")
        self.client = TavilyClient(api_key=api_key)

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        days: int = 30,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search the web using Tavily."""
        try:
            response = self.client.search(
                query=query,
                max_results=max_results,
                days=days,
                include_domains=include_domains or [],
                exclude_domains=exclude_domains or [],
                search_depth="advanced",
                include_answer=False,
                include_raw_content=False,
                include_images=False,
            )
            return response.get("results", [])
        except Exception as exc:
            raise TavilyToolError(f"Tavily search failed: {exc}") from exc


if __name__ == "__main__":
    import json
    tool = TavilyTool()
    results = tool.search("retail trader pain points information overload 2024", max_results=3)
    print(json.dumps(results, indent=2))