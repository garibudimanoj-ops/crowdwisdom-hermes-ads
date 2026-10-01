from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agents.marketing_analyzer import MarketingAnalyzer, MarketingAnalyzerError
from src.models.ad_models import AdRecord, MarketingInsight


class TestMarketingAnalyzerInit:
    def test_default_insights_path(self) -> None:
        analyzer = MarketingAnalyzer()
        assert analyzer.insights_path == Path("outputs/insights/marketing_insights.json")

    def test_custom_insights_path(self) -> None:
        custom_path = Path("/tmp/custom_insights.json")
        analyzer = MarketingAnalyzer(insights_path=custom_path)
        assert analyzer.insights_path == custom_path

    def test_custom_hermes_runner(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run.return_value = '{"hooks": []}'
        analyzer = MarketingAnalyzer(hermes_runner=mock_runner)
        assert analyzer.hermes_runner is mock_runner


class TestMarketingAnalyzerPrompt:
    def test_prompt_contains_ads_summary(self) -> None:
        analyzer = MarketingAnalyzer()
        ads = [
            AdRecord(
                ad_archive_id="arch-1",
                advertiser="Test Advertiser",
                ad_text="Buy trading signals",
                title="Trading Ad",
                platform="Meta Ads Library",
            )
        ]
        prompt = analyzer._build_analysis_prompt(ads)
        assert "Test Advertiser" in prompt
        assert "Buy trading signals" in prompt
        assert "HOOKS" in prompt
        assert "PAIN POINTS" in prompt
        assert "ICPs" in prompt
        assert "EMOTIONAL TRIGGERS" in prompt
        assert "PROMISES/OFFERS" in prompt
        assert "CTA PATTERNS" in prompt
        assert "VISUAL/CREATIVE STRUCTURES" in prompt
        assert "RECURRING PATTERNS" in prompt

    def test_prompt_requires_valid_json(self) -> None:
        analyzer = MarketingAnalyzer()
        prompt = analyzer._build_analysis_prompt([])
        assert "Return ONLY valid JSON" in prompt


class TestMarketingAnalyzerParseInsights:
    def test_parse_valid_response(self) -> None:
        analyzer = MarketingAnalyzer()
        response = '{"hooks": [{"category": "hooks", "observation": "Fear of missing out", "interpretation": "FOMO drives clicks", "evidence": ["ad 1"]}], "pain_points": [], "icps": [], "emotional_triggers": [], "promises_offers": [], "cta_patterns": [], "visual_structures": [], "recurring_patterns": []}'
        insights = analyzer._parse_insights(response)
        assert "hooks" in insights
        assert "pain_points" in insights
        assert len(insights["hooks"]) == 1
        assert insights["hooks"][0].observation == "Fear of missing out"
        assert insights["hooks"][0].interpretation == "FOMO drives clicks"
        assert insights["hooks"][0].evidence == ["ad 1"]

    def test_parse_empty_response(self) -> None:
        analyzer = MarketingAnalyzer()
        response = '{"hooks": [], "pain_points": [], "icps": [], "emotional_triggers": [], "promises_offers": [], "cta_patterns": [], "visual_structures": [], "recurring_patterns": []}'
        insights = analyzer._parse_insights(response)
        assert all(len(v) == 0 for v in insights.values())

    def test_parse_missing_category_defaults_empty(self) -> None:
        analyzer = MarketingAnalyzer()
        response = '{"hooks": [{"category": "hooks", "observation": "test", "interpretation": "test", "evidence": []}]}'
        insights = analyzer._parse_insights(response)
        assert len(insights["hooks"]) == 1
        assert len(insights["pain_points"]) == 0

    def test_parse_invalid_json_raises(self) -> None:
        analyzer = MarketingAnalyzer()
        with pytest.raises(MarketingAnalyzerError):
            analyzer._parse_insights("not valid json")

    def test_parse_partial_insight(self) -> None:
        analyzer = MarketingAnalyzer()
        response = '{"hooks": [{"observation": "test"}], "pain_points": [], "icps": [], "emotional_triggers": [], "promises_offers": [], "cta_patterns": [], "visual_structures": [], "recurring_patterns": []}'
        insights = analyzer._parse_insights(response)
        assert insights["hooks"][0].observation == "test"
        assert insights["hooks"][0].category == "hooks"


class TestMarketingAnalyzerRun:
    def _make_ads(self, count: int = 3) -> list[AdRecord]:
        return [
            AdRecord(
                ad_archive_id=f"arch-{i}",
                advertiser=f"Advertiser {i}",
                ad_text=f"Trading signal ad {i}",
                title=f"Ad Title {i}",
                platform="Meta Ads Library",
            )
            for i in range(count)
        ]

    def test_run_with_ads_list(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run.return_value = '{"hooks": [{"category": "hooks", "observation": "FOMO", "interpretation": "FOMO drives clicks", "evidence": ["ad 1"]}], "pain_points": [], "icps": [], "emotional_triggers": [], "promises_offers": [], "cta_patterns": [], "visual_structures": [], "recurring_patterns": []}'
        analyzer = MarketingAnalyzer(hermes_runner=mock_runner, insights_path="/tmp/marketing_insights.json")
        ads = self._make_ads(3)

        result = analyzer.run(ads=ads)

        assert result["ad_count"] == 3
        assert "generated_at" in result
        assert "insights" in result
        assert result["insights"]["hooks"][0]["observation"] == "FOMO"
        assert result["total_insights"] == 1

    def test_run_with_ads_path(self) -> None:
        import tempfile
        import json as json_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            ads_path = Path(tmpdir) / "ads.json"
            insights_path = Path(tmpdir) / "insights.json"

            ads = self._make_ads(2)
            ads_data = {
                "generated_at": "2026-09-25T00:00:00",
                "ads": [ad.model_dump(mode="json") for ad in ads],
            }
            with ads_path.open("w", encoding="utf-8") as f:
                json_mod.dump(ads_data, f)

            mock_runner = MagicMock()
            mock_runner.run.return_value = '{"hooks": [], "pain_points": [], "icps": [], "emotional_triggers": [], "promises_offers": [], "cta_patterns": [], "visual_structures": [], "recurring_patterns": []}'
            analyzer = MarketingAnalyzer(hermes_runner=mock_runner, insights_path=insights_path)

            result = analyzer.run(ads_path=ads_path)

            assert result["ad_count"] == 2
            assert insights_path.exists()

    def test_run_raises_on_empty_ads(self) -> None:
        analyzer = MarketingAnalyzer()
        with pytest.raises(MarketingAnalyzerError, match="No ads to analyze"):
            analyzer.run(ads=[])

    def test_run_raises_on_missing_ads_file(self) -> None:
        analyzer = MarketingAnalyzer()
        with pytest.raises(MarketingAnalyzerError, match="Ads file not found"):
            analyzer.run(ads_path="/tmp/nonexistent_ads.json")

    def test_run_lazily_creates_hermes_runner(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run.return_value = '{"hooks": [], "pain_points": [], "icps": [], "emotional_triggers": [], "promises_offers": [], "cta_patterns": [], "visual_structures": [], "recurring_patterns": []}'
        analyzer = MarketingAnalyzer(insights_path="/tmp/marketing_insights.json")

        assert analyzer.hermes_runner is None

        with patch(
            "src.agents.marketing_analyzer.HermesAgentRunner", return_value=mock_runner
        ):
            analyzer.run(ads=self._make_ads(1))

        assert analyzer.hermes_runner is mock_runner

    def test_run_raises_on_hermes_error(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run.side_effect = Exception("Hermes failed")
        analyzer = MarketingAnalyzer(hermes_runner=mock_runner, insights_path="/tmp/marketing_insights.json")

        with pytest.raises(MarketingAnalyzerError, match="Hermes analysis failed"):
            analyzer.run(ads=self._make_ads(1))

    def test_run_saves_insights_file(self) -> None:
        import tempfile
        import json as json_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            insights_path = Path(tmpdir) / "insights.json"
            mock_runner = MagicMock()
            mock_runner.run.return_value = '{"hooks": [], "pain_points": [], "icps": [], "emotional_triggers": [], "promises_offers": [], "cta_patterns": [], "visual_structures": [], "recurring_patterns": []}'
            analyzer = MarketingAnalyzer(hermes_runner=mock_runner, insights_path=insights_path)

            analyzer.run(ads=self._make_ads(1))

            assert insights_path.exists()
            with insights_path.open("r", encoding="utf-8") as f:
                saved = json_mod.load(f)
            assert "generated_at" in saved
            assert "ad_count" in saved
            assert "insights" in saved


class TestMarketingAnalyzerCompactInput:
    """Tests for the compact LLM input layer."""

    def _make_long_ad(self, ad_id: str, text_length: int) -> AdRecord:
        return AdRecord(
            ad_archive_id=ad_id,
            advertiser="Test Advertiser",
            ad_text="A" * text_length,
            title="Test Ad",
            platform="Meta Ads Library",
        )

    def _make_ads_with_ids(self, ids: list[str]) -> list[AdRecord]:
        return [
            AdRecord(
                ad_archive_id=ad_id,
                advertiser=f"Advertiser {ad_id}",
                ad_text=f"Ad text for {ad_id}",
                title=f"Title {ad_id}",
                platform="Meta Ads Library",
                link_url=f"https://example.com/{ad_id}",
                start_date=20260101 + i,
                end_date=20261231,
            )
            for i, ad_id in enumerate(ids)
        ]

    def test_compact_ad_truncates_long_text(self) -> None:
        analyzer = MarketingAnalyzer(max_ad_text_chars=100)
        ad = self._make_long_ad("arch-1", 500)
        compact = analyzer._compact_ad(ad)
        # 100 chars + "... [truncated]" (15 chars) = 115
        assert len(compact["ad_text"]) <= 115
        assert compact["ad_text"].endswith("... [truncated]")

    def test_compact_ad_keeps_short_text_intact(self) -> None:
        analyzer = MarketingAnalyzer(max_ad_text_chars=100)
        ad = self._make_long_ad("arch-1", 50)
        compact = analyzer._compact_ad(ad)
        assert compact["ad_text"] == "A" * 50
        assert not compact["ad_text"].endswith("... [truncated]")

    def test_compact_ad_includes_required_fields(self) -> None:
        analyzer = MarketingAnalyzer()
        ad = AdRecord(
            ad_archive_id="arch-123",
            advertiser="Test Corp",
            ad_text="Buy now!",
            title="Sale",
            platform="Meta Ads Library",
            link_url="https://test.com/landing",
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        compact = analyzer._compact_ad(ad)
        assert compact["ad_id"] == "arch-123"
        assert compact["advertiser"] == "Test Corp"
        assert compact["ad_text"] == "Buy now!"
        assert compact["start_date"] == "2026-01-01"
        assert compact["end_date"] == "2026-12-31"
        assert compact["platform"] == "Meta Ads Library"
        assert compact["landing_page"] == "https://test.com/landing"

    def test_deduplicate_ads_by_ad_archive_id(self) -> None:
        analyzer = MarketingAnalyzer()
        ads = self._make_ads_with_ids(["arch-1", "arch-2", "arch-1", "arch-3", "arch-2"])
        unique = analyzer._deduplicate_ads(ads)
        assert len(unique) == 3
        assert [a.ad_archive_id for a in unique] == ["arch-1", "arch-2", "arch-3"]

    def test_prepare_ads_limits_to_max_ads(self) -> None:
        analyzer = MarketingAnalyzer(max_ads=3)
        ads = self._make_ads_with_ids([f"arch-{i}" for i in range(10)])
        compact = analyzer._prepare_ads_for_llm(ads)
        assert len(compact) == 3

    def test_prepare_ads_sorts_by_start_date_descending(self) -> None:
        analyzer = MarketingAnalyzer(max_ads=5)
        ads = self._make_ads_with_ids(["arch-1", "arch-2", "arch-3"])
        # Different start dates: arch-1 has 20260101, arch-2 has 20260102, arch-3 has 20260103
        compact = analyzer._prepare_ads_for_llm(ads)
        # Should be sorted descending (most recent first): arch-3, arch-2, arch-1
        assert [c["ad_id"] for c in compact] == ["arch-3", "arch-2", "arch-1"]

    def test_prompt_stays_within_budget(self) -> None:
        analyzer = MarketingAnalyzer(max_ads=20, max_ad_text_chars=500, prompt_budget_chars=8000)
        ads = self._make_ads_with_ids([f"arch-{i}" for i in range(30)])
        compact = analyzer._prepare_ads_for_llm(ads)
        prompt = analyzer._build_analysis_prompt(compact)
        assert len(prompt) <= analyzer.prompt_budget_chars + 50  # small tolerance

    def test_prompt_budget_enforced_even_with_many_ads(self) -> None:
        # Very small budget to force truncation
        analyzer = MarketingAnalyzer(max_ads=10, max_ad_text_chars=2000, prompt_budget_chars=1000)
        ads = self._make_ads_with_ids([f"arch-{i}" for i in range(20)])
        compact = analyzer._prepare_ads_for_llm(ads)
        prompt = analyzer._build_analysis_prompt(compact)
        assert len(prompt) <= 1050  # budget + small tolerance for truncation marker

    def test_compact_ads_excludes_source_metadata(self) -> None:
        analyzer = MarketingAnalyzer()
        ad = AdRecord(
            ad_archive_id="arch-1",
            advertiser="Test",
            ad_text="Text",
            title="Title",
            platform="Meta Ads Library",
            source_metadata={"huge": "data" * 1000},
        )
        compact = analyzer._compact_ad(ad)
        assert "source_metadata" not in compact
        # Verify no large nested structures leaked
        assert len(json.dumps(compact)) < 1000

    def test_provenance_uses_compact_ad_ids(self) -> None:
        analyzer = MarketingAnalyzer()
        ads = self._make_ads_with_ids(["arch-1", "arch-2", "arch-3"])
        compact = analyzer._prepare_ads_for_llm(ads)
        # Simulate insight with evidence referencing compact ad position
        from src.models.ad_models import MarketingInsight

        insights = {
            "hooks": [
                MarketingInsight(
                    category="hooks",
                    observation="Test hook",
                    interpretation="Test",
                    evidence=["ad 2"],  # References compact[1] -> arch-2
                )
            ],
            "pain_points": [],
            "icps": [],
            "emotional_triggers": [],
            "promises_offers": [],
            "cta_patterns": [],
            "visual_structures": [],
            "recurring_patterns": [],
        }
        enriched = analyzer._enrich_with_provenance(insights, compact)
        assert enriched["hooks"][0].source_ad_id == "arch-2"
        assert enriched["hooks"][0].advertiser == "Advertiser arch-2"
        assert enriched["hooks"][0].source_url == "https://example.com/arch-2"

    def test_no_fabricated_performance_metrics_in_ad_content(self) -> None:
        analyzer = MarketingAnalyzer()
        ads = self._make_ads_with_ids(["arch-1"])
        compact = analyzer._prepare_ads_for_llm(ads)
        prompt = analyzer._build_analysis_prompt(compact)
        # Check only the ADS TO ANALYZE section for fabricated metrics (not constraint text)
        ads_section = prompt.split("ADS TO ANALYZE:")[1]
        forbidden = ["ctr", "roas", "conversion", "spend", "cpa", "cpm", "clicks", "impressions", "best-performing"]
        ads_lower = ads_section.lower()
        for term in forbidden:
            assert term not in ads_lower, f"Forbidden term '{term}' found in ad content section"

    def test_heuristic_label_when_no_performance_data(self) -> None:
        analyzer = MarketingAnalyzer()
        ads = self._make_ads_with_ids(["arch-1"])
        compact = analyzer._prepare_ads_for_llm(ads)
        prompt = analyzer._build_analysis_prompt(compact)
        # Should contain constraint about not inventing stats
        assert "Do NOT invent statistics" in prompt
        assert "Do NOT claim patterns" in prompt

    def test_empty_ad_text_handled(self) -> None:
        analyzer = MarketingAnalyzer()
        ad = AdRecord(
            ad_archive_id="arch-1",
            advertiser="Test",
            ad_text="",
            title="Title",
            platform="Meta Ads Library",
        )
        compact = analyzer._compact_ad(ad)
        assert compact["ad_text"] == ""

    def test_none_ad_text_handled(self) -> None:
        analyzer = MarketingAnalyzer()
        ad = AdRecord(
            ad_archive_id="arch-1",
            advertiser="Test",
            ad_text=None,
            title="Title",
            platform="Meta Ads Library",
        )
        compact = analyzer._compact_ad(ad)
        assert compact["ad_text"] == ""

    def test_missing_optional_fields_handled(self) -> None:
        analyzer = MarketingAnalyzer()
        ad = AdRecord(
            ad_archive_id="arch-1",
            advertiser="Test",
            ad_text="Text",
        )
        compact = analyzer._compact_ad(ad)
        assert compact["ad_id"] == "arch-1"
        assert compact["advertiser"] == "Test"
        assert compact["ad_text"] == "Text"
        assert compact["start_date"] is None
        assert compact["end_date"] is None
        assert compact["platform"] is None
        assert compact["landing_page"] is None