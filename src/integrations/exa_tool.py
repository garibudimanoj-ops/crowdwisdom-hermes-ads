from __future__ import annotations

import os
from typing import Any

from exa_py import Exa


class ExaToolError(RuntimeError):
    """Raised when an Exa search operation fails."""


class ExaTool:
    """Wrapper around Exa API for web search."""

    def __init__(self) -> None:
        api_key = os.getenv("EXA_API_KEY")
        if not api_key:
            raise ExaToolError("EXA_API_KEY is missing from the environment.")
        self.client = Exa(api_key=api_key)

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        days: int = 30,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        type: str = "auto",
    ) -> list[dict[str, Any]]:
        """Search the web using Exa."""
        try:
            kwargs: dict[str, Any] = {
                "query": query,
                "num_results": max_results,
                "type": type,
                "include_domains": include_domains or [],
                "exclude_domains": exclude_domains or [],
                "start_published_date": "",
                "end_published_date": "",
            }
            if days > 0:
                kwargs["start_published_date"] = f"{days}d"
            response = self.client.search(**kwargs)
            results = []
            for item in getattr(response, "results", []):
                results.append(
                    {
                        "title": getattr(item, "title", ""),
                        "url": getattr(item, "url", ""),
                        "published_date": getattr(item, "published_date", None),
                        "text": getattr(item, "text", ""),
                        "source": "Exa",
                    }
                )
            return results
        except Exception as exc:
            raise ExaToolError(f"Exa search failed: {exc}") from exc


if __name__ == "__main__":
    import json
    tool = ExaTool()
    results = tool.search("retail trader pain points information overload", max_results=3)
    print(json.dumps(results, indent=2))