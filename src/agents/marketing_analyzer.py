from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from src.integrations.hermes_runner import HermesAgentRunner, HermesError
from src.models.ad_models import AdRecord, MarketingInsight


class MarketingAnalyzerError(RuntimeError):
    """Raised when marketing analysis fails."""


class MarketingAnalyzer:
    """Analyze collected ads to extract marketing patterns using Hermes."""

    DEFAULT_INSIGHTS_PATH = Path("outputs/insights/marketing_insights.json")
    DEFAULT_MAX_ADS = 20
    DEFAULT_MAX_AD_TEXT_CHARS = 500
    DEFAULT_PROMPT_BUDGET_CHARS = 8000

    def __init__(
        self,
        hermes_runner: HermesAgentRunner | None = None,
        insights_path: Path | str | None = None,
        max_ads: int | None = None,
        max_ad_text_chars: int | None = None,
        prompt_budget_chars: int | None = None,
    ) -> None:
        self.hermes_runner = hermes_runner
        self.insights_path = Path(insights_path or self.DEFAULT_INSIGHTS_PATH)
        self.max_ads = max_ads or self.DEFAULT_MAX_ADS
        self.max_ad_text_chars = max_ad_text_chars or self.DEFAULT_MAX_AD_TEXT_CHARS
        self.prompt_budget_chars = prompt_budget_chars or self.DEFAULT_PROMPT_BUDGET_CHARS

    def _compact_ad(self, ad: AdRecord) -> dict[str, Any]:
        """Extract only essential fields from an AdRecord for LLM input."""
        ad_text = ad.ad_text or ""
        if len(ad_text) > self.max_ad_text_chars:
            ad_text = ad_text[: self.max_ad_text_chars] + "... [truncated]"
        return {
            "ad_id": ad.ad_archive_id,
            "advertiser": ad.advertiser,
            "ad_text": ad_text,
            "start_date": ad.start_date,
            "end_date": ad.end_date,
            "platform": ad.platform,
            "landing_page": ad.link_url,
        }

    def _deduplicate_ads(self, ads: list[AdRecord]) -> list[AdRecord]:
        """Remove duplicate ads by ad_archive_id, keeping the first occurrence."""
        seen = set()
        unique = []
        for ad in ads:
            ad_id = ad.ad_archive_id
            if ad_id and ad_id not in seen:
                seen.add(ad_id)
                unique.append(ad)
        return unique

    def _prepare_ads_for_llm(self, ads: list[AdRecord]) -> list[dict[str, Any]]:
        """Prepare ads for LLM: deduplicate, limit count, extract compact fields."""
        # Deduplicate by ad_archive_id
        unique_ads = self._deduplicate_ads(ads)
        # Sort by start_date descending (most recent first), handling None
        def sort_key(ad: AdRecord) -> int:
            try:
                sd = ad.start_date
                if sd is None:
                    return 0
                if isinstance(sd, str):
                    return int(sd)
                return int(sd)
            except (ValueError, TypeError):
                return 0

        unique_ads.sort(key=sort_key, reverse=True)
        # Limit to max_ads
        limited_ads = unique_ads[: self.max_ads]
        # Build compact representation
        return [self._compact_ad(ad) for ad in limited_ads]

    def _build_analysis_prompt(self, ads: list[dict[str, Any] | AdRecord]) -> str:
        """Build the analysis prompt for Hermes from compact ad records.

        Accepts either compact dict records or full AdRecord objects (for
        backward compatibility with existing callers).
        """
        def _get(ad: dict[str, Any] | AdRecord, key: str) -> Any:
            if isinstance(ad, dict):
                return ad.get(key)
            return getattr(ad, key, None)

        ads_summary = []
        for i, ad in enumerate(ads):
            ad_id = _get(ad, "ad_id") or f"unknown-{i+1}"
            ads_summary.append(
                f"Ad {i+1} (id: {ad_id}):\n"
                f"  Advertiser: {_get(ad, 'advertiser') or 'Unknown'}\n"
                f"  Ad Text: {_get(ad, 'ad_text') or ''}\n"
                f"  Start Date: {_get(ad, 'start_date') or 'Unknown'}\n"
                f"  End Date: {_get(ad, 'end_date') or 'Unknown'}\n"
                f"  Platform: {_get(ad, 'platform') or 'Unknown'}\n"
                f"  Landing Page: {_get(ad, 'landing_page') or 'Unknown'}\n"
            )

        sample_warning = (
            "\n\n*** CRITICAL CONSTRAINT ***\n"
            f"You are analyzing ONLY {len(ads)} ad(s).\n"
            "All conclusions must be marked with 'single_ad_observation'.\n"
            "Confidence should be marked as 'confidence: low'.\n"
            "Do NOT claim patterns, preferences, or generalities that cannot be supported by the actual ad content.\n"
            "Do NOT invent statistics about performance, reach, or effectiveness.\n"
            "Only discuss what is explicitly present in the provided ad text, title, and metadata.\n"
            "If you cannot safely infer something from the single ad, state 'cannot determine from available data'.\n"
            "---\n"
        ) if len(ads) == 1 else "\n\n"

        prompt_body = (
            "You are a senior marketing analyst specializing in financial/trading advertising.\n"
            "Analyze the following Meta Ads Library ads for trading/investing products.\n"
            "Extract structured insights across these categories:\n"
            "1. HOOKS - Opening angles that grab attention in first 1-3 seconds\n"
            "2. PAIN POINTS - Customer problems, frustrations, fears addressed\n"
            "3. ICPs - Ideal Customer Profiles (demographics, behaviors, psychographics)\n"
            "4. EMOTIONAL TRIGGERS - Fear, greed, FOMO, hope, security, status\n"
            "5. PROMISES/OFFERS - Specific value propositions, guarantees, outcomes\n"
            "6. CTA PATTERNS - Call-to-action types, urgency signals, friction reducers\n"
            "7. VISUAL/CREATIVE STRUCTURES - Ad formats, visual styles, narrative arcs\n"
            "8. RECURRING PATTERNS - Themes appearing across multiple ads (note: single ad analysis)\n\n"
            "Return ONLY valid JSON matching this schema:\n"
            "{\n"
            "  \"hooks\": [\n"
            "    {\"category\": \"hooks\", \"observation\": \"...\", \"interpretation\": \"...\", \"evidence\": [\"ad 1\"]}\n"
            "  ],\n"
            "  \"pain_points\": [...],\n"
            "  \"icps\": [...],\n"
            "  \"emotional_triggers\": [...],\n"
            "  \"promises_offers\": [...],\n"
            "  \"cta_patterns\": [...],\n"
            "  \"visual_structures\": [...],\n"
            "  \"recurring_patterns\": [...]\n"
            "}\n\n"
            "IMPORTANT GUIDELINES:\n"
            "- Evidence should reference specific ads by number (e.g., \"ad 1\").\n"
            "- Mark ALL insights with 'single_ad_observation' if this is the only ad.\n"
            "- Mark confidence as 'confidence: low' for all insights from a single ad.\n"
            "- Do NOT claim patterns, preferences, or generalities without direct evidence.\n"
            "- Do NOT invent statistics or make claims about performance, reach, or effectiveness.\n"
            "- Only discuss what's explicitly present in the ad content.\n"
            "- For \"recurring_patterns\", note that this is based on a single ad and may not represent actual patterns across the market.\n"
            "- Each insight object must have: category, observation, interpretation, evidence (list of ad references).\n"
            "- Be specific. Quote actual ad text. No generic fluff.\n\n"
            f"ADS TO ANALYZE:\n{''.join(ads_summary)}{sample_warning}"
        )

        # Verify prompt fits budget
        if len(prompt_body) > self.prompt_budget_chars:
            # This should not happen with proper limits, but truncate if needed
            prompt_body = prompt_body[: self.prompt_budget_chars] + "\n... [prompt truncated to budget]"

        return prompt_body

    def _parse_insights(self, response: str) -> dict[str, list[MarketingInsight]]:
        """Parse Hermes response into structured insights."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError as exc:
            raise MarketingAnalyzerError(f"Failed to parse Hermes JSON: {exc}") from exc

        categories = [
            "hooks",
            "pain_points",
            "icps",
            "emotional_triggers",
            "promises_offers",
            "cta_patterns",
            "visual_structures",
            "recurring_patterns",
        ]

        result: dict[str, list[MarketingInsight]] = {}
        for cat in categories:
            items = data.get(cat, [])
            result[cat] = []
            for item in items:
                if isinstance(item, dict):
                    single_ad = len(items) == 1 or all("ad 1" in str(e) for e in item.get("evidence", []))
                    insight = MarketingInsight(
                        category=item.get("category", cat),
                        observation=item.get("observation", ""),
                        interpretation=item.get("interpretation", ""),
                        evidence=item.get("evidence", []),
                        source_ad_id=None,
                        source_url=None,
                        retrieved_at=None,
                        source_field=None,
                        advertiser=None,
                        source_fact=False,
                        single_ad_observation=single_ad,
                    )
                    if "confidence" in item and isinstance(item["confidence"], str):
                        insight.confidence = item["confidence"]
                    if item.get("evidence"):
                        insight.evidence = item["evidence"]
                    result[cat].append(insight)
        return result

    def _enrich_with_provenance(
        self,
        insights: dict[str, list[MarketingInsight]],
        ads: list[dict[str, Any]],
    ) -> dict[str, list[MarketingInsight]]:
        """Add source metadata to each insight from the compact ad record."""
        for cat, items in insights.items():
            for item in items:
                if item.evidence:
                    for ref in item.evidence:
                        try:
                            idx = int(ref.split()[-1]) - 1
                            if 0 <= idx < len(ads):
                                ad = ads[idx]
                                item.source_ad_id = ad.get("ad_id")
                                item.source_url = ad.get("landing_page")
                                item.advertiser = ad.get("advertiser")
                                item.retrieved_at = ad.get("start_date")
                                item.source_field = "ad_text"
                        except (ValueError, IndexError):
                            pass
        return insights

    def _validate_insights(
        self,
        insights: dict[str, list[MarketingInsight]],
    ) -> list[str]:
        """Validate insights and return list of warnings/limitations."""
        warnings = []
        total_insights = sum(len(v) for v in insights.values())
        if total_insights == 0:
            warnings.append("No insights generated from the Hermes response.")
        for cat, items in insights.items():
            for item in items:
                if not item.observation:
                    warnings.append(f"Empty observation in category '{cat}'.")
                if not item.evidence:
                    warnings.append(f"No evidence provided for '{cat}': {item.observation[:50]}")
        return warnings

    def run(self, ads: list[AdRecord] | None = None, ads_path: Path | str | None = None) -> dict[str, Any]:
        """Run marketing analysis on ads and save insights."""
        if ads is None:
            if ads_path is None:
                ads_path = Path("outputs/ads/ads.json")
            ads_path = Path(ads_path)
            if not ads_path.exists():
                raise MarketingAnalyzerError(f"Ads file not found: {ads_path}")
            with ads_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            ads = [AdRecord.model_validate(ad) for ad in data.get("ads", [])]

        if not ads:
            raise MarketingAnalyzerError("No ads to analyze")

        if self.hermes_runner is None:
            self.hermes_runner = HermesAgentRunner()

        # Prepare compact ads for LLM
        compact_ads = self._prepare_ads_for_llm(ads)

        prompt = self._build_analysis_prompt(compact_ads)

        system_prompt = (
            "You are a senior marketing analyst. Return only valid JSON. "
            "No markdown, no explanations, no extra text."
        )

        try:
            response = self.hermes_runner.run(prompt, system_prompt=system_prompt)
        except HermesError as exc:
            raise MarketingAnalyzerError(f"Hermes analysis failed: {exc}") from exc
        except Exception as exc:
            raise MarketingAnalyzerError(f"Hermes analysis failed: {exc}") from exc

        insights = self._parse_insights(response)
        insights = self._enrich_with_provenance(insights, compact_ads)
        warnings = self._validate_insights(insights)

        total_insights = sum(len(v) for v in insights.values())

        result = {
            "generated_at": datetime.now().isoformat(),
            "source_file": str(ads_path) if ads_path else "outputs/ads/ads.json",
            "ads_analyzed": len(compact_ads),
            "ad_count": len(compact_ads),
            "total_insights": total_insights,
            "insights": {k: [i.model_dump(mode="json") for i in v] for k, v in insights.items()},
            "limitations": warnings,
            "source_metadata": {
                "platform": "Meta Ads Library",
                "actor": "apify/facebook-ads-scraper",
                "sdk_version": "3.2.0",
            },
        }

        self.insights_path.parent.mkdir(parents=True, exist_ok=True)
        with self.insights_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result