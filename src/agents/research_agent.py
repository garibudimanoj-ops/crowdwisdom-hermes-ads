from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.integrations.exa_tool import ExaTool
from src.integrations.tavily_tool import TavilyTool

logger = logging.getLogger(__name__)


class ResearchAgentError(RuntimeError):
    """Raised when research agent operations fail."""


class ResearchAgent:
    """Research Agent for gathering additional market research based on marketing insights."""

    def __init__(self, *, tavily_tool: TavilyTool | None = None, exa_tool: ExaTool | None = None) -> None:
        self.tavily = tavily_tool or TavilyTool()
        self.exa = exa_tool or ExaTool()

    def _load_marketing_insights(self) -> dict[str, Any]:
        """Load marketing insights from the analyzer output."""
        insights_path = Path("outputs/insights/marketing_insights.json")
        if not insights_path.exists():
            raise ResearchAgentError(f"Marketing insights not found at {insights_path}")
        with insights_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _extract_research_queries(self, insights_data: dict[str, Any]) -> list[dict[str, str]]:
        """Extract research queries from marketing insights.

        Queries are derived from actual observations in the insights,
        not fabricated. Each query is tagged with its source category
        and single_ad_observation flag where applicable.
        """
        queries = []
        insights = insights_data.get("insights", {})
        source_metadata = insights_data.get("source_metadata", {})

        # Extract from pain_points category
        for item in insights.get("pain_points", []):
            if isinstance(item, dict):
                observation = item.get("observation", "")
                if observation:
                    queries.append(
                        {
                            "query": observation,
                            "type": "pain_point",
                            "source": "marketing_insights",
                            "source_ad_id": item.get("source_ad_id"),
                            "single_ad_observation": item.get("single_ad_observation", False),
                            "confidence": item.get("confidence", "unknown"),
                        }
                    )

        # Extract from ICPs category
        for item in insights.get("icps", []):
            if isinstance(item, dict):
                observation = item.get("observation", "")
                if observation:
                    queries.append(
                        {
                            "query": observation,
                            "type": "icp",
                            "source": "marketing_insights",
                            "source_ad_id": item.get("source_ad_id"),
                            "single_ad_observation": item.get("single_ad_observation", False),
                            "confidence": item.get("confidence", "unknown"),
                        }
                    )

        # Extract from hooks category - research the claimed credibility/authority
        for item in insights.get("hooks", []):
            if isinstance(item, dict):
                observation = item.get("observation", "")
                if observation:
                    queries.append(
                        {
                            "query": observation,
                            "type": "hook_credibility",
                            "source": "marketing_insights",
                            "source_ad_id": item.get("source_ad_id"),
                            "single_ad_observation": item.get("single_ad_observation", False),
                            "confidence": item.get("confidence", "unknown"),
                        }
                    )

        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            query_key = (q["query"], q["type"], q["source"])
            if query_key not in seen:
                seen.add(query_key)
                unique_queries.append(q)

        return unique_queries

    def _search_with_fallback(self, query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
        """Try Tavily first, then Exa as fallback."""
        tavily_error: Exception | None = None

        # Try Tavily first
        try:
            logger.info("Attempting Tavily search: %s", query[:100])
            return self.tavily.search(query, max_results=max_results, days=30)
        except Exception as exc:  # pylint: disable=broad-except
            tavily_error = exc
            logger.warning("Tavily search failed: %s. Trying Exa fallback.", exc)

        # Try Exa as fallback
        try:
            logger.info("Attempting Exa search: %s", query[:100])
            return self.exa.search(query, max_results=max_results, days=30)
        except Exception as exa_error:  # pylint: disable=broad-except
            logger.error("Both Tavily and Exa search failed: Tavily=%s, Exa=%s", tavily_error, exa_error)
            return []

    def _enrich_result(self, result: dict[str, Any], query_info: dict[str, str], provider: str) -> dict[str, Any]:
        """Enrich a search result with provenance metadata."""
        return {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "source": provider,
            "published_date": result.get("published_date") or result.get("publishedAt"),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "query": query_info["query"],
            "query_type": query_info["type"],
            "source_fact": True,
            "model_interpretation": False,
        }

    def run(self) -> dict[str, Any]:
        """Execute the research agent workflow."""
        logger.info("Starting Research Agent")

        # Load marketing insights
        insights_data = self._load_marketing_insights()
        ad_insights = insights_data.get("insights", {}).get("ad_insights", [])
        logger.info("Loaded marketing insights with %d ads", len(ad_insights))

        # Extract research queries
        research_queries = self._extract_research_queries(insights_data)
        logger.info("Extracted %d research queries", len(research_queries))

        # Check if this is a single-ad observation
        single_ad = any(q.get("single_ad_observation") for q in research_queries)
        ads_analyzed = insights_data.get("ads_analyzed", 1)

        # Execute searches
        research_results = []
        for query_info in research_queries:
            query = query_info["query"]
            logger.info("Researching: %s", query[:100])

            search_results = self._search_with_fallback(query, max_results=5)

            enriched_results = [
                self._enrich_result(result, query_info, "Tavily" if result.get("source") != "Exa" else "Exa")
                for result in search_results
            ]

            research_results.append(
                {
                    "query": query,
                    "query_type": query_info["type"],
                    "query_source": query_info["source"],
                    "single_ad_observation": query_info.get("single_ad_observation", False),
                    "confidence": query_info.get("confidence", "unknown"),
                    "results": enriched_results,
                    "result_count": len(enriched_results),
                }
            )

        # Compile final research output
        research_output = {
            "research_metadata": {
                "source_insights_file": "outputs/insights/marketing_insights.json",
                "total_queries": len(research_queries),
                "total_results": sum(r["result_count"] for r in research_results),
                "tavily_available": True,
                "exa_available": True,
                "ads_analyzed": ads_analyzed,
                "single_ad_observation": single_ad,
                "limitation": (
                    "Upstream marketing evidence came from a single relevant advertisement. "
                    "Research findings should not be generalized to market-wide patterns "
                    "without additional evidence."
                ),
            },
            "research_findings": research_results,
        }

        # Save research output
        output_dir = Path("outputs/research")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "research.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(research_output, f, indent=2, ensure_ascii=False)

        logger.info("Research completed. Results saved to %s", output_path)
        return research_output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = ResearchAgent()
    result = agent.run()
    print(f"Research completed with {result['research_metadata']['total_results']} total results")