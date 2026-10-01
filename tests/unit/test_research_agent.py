from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agents.research_agent import ResearchAgent
from src.integrations.exa_tool import ExaTool
from src.integrations.tavily_tool import TavilyTool


@pytest.fixture
def mock_tavily_tool():
    return MagicMock(spec=TavilyTool)


@pytest.fixture
def mock_exa_tool():
    return MagicMock(spec=ExaTool)


@pytest.fixture
def research_agent(mock_tavily_tool, mock_exa_tool):
    return ResearchAgent(tavily_tool=mock_tavily_tool, exa_tool=mock_exa_tool)


@pytest.fixture
def sample_marketing_insights():
    return {
        "generated_at": "2026-09-25T13:52:13.830638",
        "source_file": "outputs/ads/ads.json",
        "ads_analyzed": 1,
        "ad_count": 1,
        "total_insights": 8,
        "insights": {
            "hooks": [
                {
                    "category": "hooks",
                    "observation": "The ad opens with the announcement: 'FundedNext has won the Deloitte Technology Fast 50.'",
                    "confidence": "low",
                    "source_ad_id": "2029795367917171",
                    "single_ad_observation": True,
                }
            ],
            "pain_points": [
                {
                    "category": "pain_points",
                    "observation": "The ad copy does not mention any specific customer problems, frustrations, fears, or challenges.",
                    "confidence": "low",
                    "source_ad_id": "2029795367917171",
                    "single_ad_observation": True,
                }
            ],
            "icps": [
                {
                    "category": "icps",
                    "observation": "The ad does not specify any demographic, behavioral, or psychographic characteristics of the target audience.",
                    "confidence": "low",
                    "source_ad_id": "2029795367917171",
                    "single_ad_observation": True,
                }
            ],
            "ad_insights": [
                {
                    "ad_id": "2029795367917171",
                    "advertiser": "FundedNext Global",
                    "pain_points": [],
                    "icp": [],
                }
            ],
        },
        "source_metadata": {
            "platform": "Meta Ads Library",
            "actor": "apify/facebook-ads-scraper",
        },
    }


def test_research_agent_initialization(research_agent, mock_tavily_tool, mock_exa_tool):
    """Test that ResearchAgent initializes with provided tools."""
    assert research_agent.tavily == mock_tavily_tool
    assert research_agent.exa == mock_exa_tool


def test_research_agent_loads_marketing_insights(research_agent, tmp_path: Path, sample_marketing_insights):
    """Test loading marketing insights from file."""
    insights_dir = tmp_path / "outputs" / "insights"
    insights_dir.mkdir(parents=True)
    insights_file = insights_dir / "marketing_insights.json"
    insights_file.write_text(json.dumps(sample_marketing_insights), encoding="utf-8")

    # Change working directory to tmp_path for test
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        insights_data = research_agent._load_marketing_insights()
        assert insights_data == sample_marketing_insights
    finally:
        os.chdir(original_cwd)


def test_research_agent_extracts_research_queries(research_agent, sample_marketing_insights):
    """Test extracting research queries from marketing insights."""
    queries = research_agent._extract_research_queries(sample_marketing_insights)
    assert len(queries) == 3  # 1 hook + 1 pain point + 1 ICP

    # Check query types and sources
    query_types = [q["type"] for q in queries]
    assert "hook_credibility" in query_types
    assert "pain_point" in query_types
    assert "icp" in query_types

    # Check single-ad observation flags
    assert all(q["single_ad_observation"] for q in queries)
    assert all(q["source_ad_id"] == "2029795367917171" for q in queries)


def test_research_agent_search_with_fallback_tavily_first(research_agent, mock_tavily_tool, mock_exa_tool):
    """Test that search tries Tavily first, then Exa as fallback."""
    # Configure mocks
    mock_tavily_tool.search.return_value = [{"title": "Tavily Result", "url": "http://tavily.com"}]
    mock_exa_tool.search.return_value = [{"title": "Exa Result", "url": "http://exa.com"}]

    # Execute search
    results = research_agent._search_with_fallback("test query", max_results=5)

    # Verify Tavily was called first
    mock_tavily_tool.search.assert_called_once_with("test query", max_results=5, days=30)
    # Exa should not be called if Tavily succeeds
    mock_exa_tool.search.assert_not_called()

    # Verify results came from Tavily
    assert len(results) == 1
    assert results[0]["title"] == "Tavily Result"


def test_research_agent_search_with_fallback_to_exa(research_agent, mock_tavily_tool, mock_exa_tool):
    """Test that search falls back to Exa when Tavily fails."""
    # Configure mocks - Tavily fails, Exa succeeds
    mock_tavily_tool.search.side_effect = Exception("Tavily API error")
    mock_exa_tool.search.return_value = [{"title": "Exa Result", "url": "http://exa.com"}]

    # Execute search
    results = research_agent._search_with_fallback("test query", max_results=5)

    # Verify both were called
    mock_tavily_tool.search.assert_called_once_with("test query", max_results=5, days=30)
    mock_exa_tool.search.assert_called_once_with("test query", max_results=5, days=30)

    # Verify results came from Exa
    assert len(results) == 1
    assert results[0]["title"] == "Exa Result"


def test_research_agent_search_both_fail(research_agent, mock_tavily_tool, mock_exa_tool):
    """Test that search returns empty list when both Tavily and Exa fail."""
    # Configure mocks - both fail
    mock_tavily_tool.search.side_effect = Exception("Tavily API error")
    mock_exa_tool.search.side_effect = Exception("Exa API error")

    # Execute search
    results = research_agent._search_with_fallback("test query", max_results=5)

    # Verify both were called
    mock_tavily_tool.search.assert_called_once()
    mock_exa_tool.search.assert_called_once()

    # Verify empty results
    assert results == []


def test_research_agent_enrich_result_provenance(research_agent):
    """Test that search results are enriched with provenance metadata."""
    query_info = {
        "query": "test query",
        "type": "pain_point",
        "source": "marketing_insights",
        "source_ad_id": "2029795367917171",
        "single_ad_observation": True,
        "confidence": "low",
    }
    result = {
        "title": "Test Result",
        "url": "http://example.com",
        "published_date": "2026-09-25",
    }

    enriched = research_agent._enrich_result(result, query_info, "Tavily")

    assert enriched["title"] == "Test Result"
    assert enriched["url"] == "http://example.com"
    assert enriched["source"] == "Tavily"
    assert enriched["published_date"] == "2026-09-25"
    assert enriched["retrieved_at"]
    assert enriched["query"] == "test query"
    assert enriched["query_type"] == "pain_point"
    assert enriched["source_fact"] is True
    assert enriched["model_interpretation"] is False


@patch("src.agents.research_agent.logging")
def test_research_agent_run_success(mock_logging, research_agent, mock_tavily_tool, mock_exa_tool, tmp_path: Path, sample_marketing_insights):
    """Test successful execution of the research agent."""
    # Setup directory structure
    outputs_dir = tmp_path / "outputs"
    insights_dir = outputs_dir / "insights"
    research_dir = outputs_dir / "research"
    insights_dir.mkdir(parents=True)
    research_dir.mkdir(parents=True)

    # Write sample marketing insights
    insights_file = insights_dir / "marketing_insights.json"
    insights_file.write_text(json.dumps(sample_marketing_insights), encoding="utf-8")

    # Configure mock search results
    mock_tavily_tool.search.return_value = [
        {"title": "Test Result 1", "url": "http://example.com/1", "content": "Test content 1"},
        {"title": "Test Result 2", "url": "http://example.com/2", "content": "Test content 2"},
    ]
    mock_exa_tool.search.return_value = []  # Not used since Tavily succeeds

    # Change working directory to tmp_path
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Run the agent
        result = research_agent.run()

        # Verify result structure
        assert "research_metadata" in result
        assert "research_findings" in result
        assert result["research_metadata"]["total_queries"] == 3
        assert result["research_metadata"]["total_results"] == 6  # 3 queries * 2 results each
        assert result["research_metadata"]["ads_analyzed"] == 1
        assert result["research_metadata"]["single_ad_observation"] is True
        assert "limitation" in result["research_metadata"]

        # Verify research findings
        assert len(result["research_findings"]) == 3
        for finding in result["research_findings"]:
            assert "query" in finding
            assert "results" in finding
            assert "result_count" in finding
            assert finding["result_count"] == 2
            assert finding["single_ad_observation"] is True

        # Verify output file was created
        output_file = Path("outputs/research/research.json")
        assert output_file.exists()
        with output_file.open("r", encoding="utf-8") as f:
            saved_result = json.load(f)
        assert saved_result == result

    finally:
        os.chdir(original_cwd)


def test_research_agent_handles_missing_insights_file(research_agent, tmp_path: Path):
    """Test that research agent handles missing insights file gracefully."""
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        with pytest.raises(Exception, match="Marketing insights not found"):
            research_agent._load_marketing_insights()
    finally:
        os.chdir(original_cwd)