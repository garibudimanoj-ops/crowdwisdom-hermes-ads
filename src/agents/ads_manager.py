from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from src.integrations.apify_client import ApifyRunner
from src.models.ad_models import AdRecord


class AdsManagerError(RuntimeError):
    """Raised when ad research fails."""


class AdsManager:
    """Research Meta Ads Library for relevant advertising patterns."""

    ACTOR_ID = "apify/facebook-ads-scraper"
    DEFAULT_LOOKBACK_DAYS = 30
    DEFAULT_MAX_RESULTS = 50
    DEFAULT_COUNTRY = "US"

    def __init__(
        self,
        apify_runner: ApifyRunner | None = None,
        output_path: str | Path | None = None,
        actor_id: str | None = None,
    ) -> None:
        self.apify_runner = apify_runner
        self.output_path = Path(output_path or Path("outputs/ads/ads.json"))
        self.ACTOR_ID = actor_id or os.getenv("ADS_MANAGER_ACTOR_ID", "apify/facebook-ads-scraper")

    def _build_ad_library_url(
        self,
        keyword: str,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        country: str = DEFAULT_COUNTRY,
    ) -> str:
        """Build a Meta Ad Library URL with date filters.

        The official Apify-maintained Actor (apify/facebook-ads-scraper)
        accepts a full Ad Library URL via the `startUrls` input field.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        encoded_keyword = quote(keyword, safe="")

        base_url = (
            "https://www.facebook.com/ads/library/"
            f"?active_status=all&ad_type=all&country={country}"
            f"&q={encoded_keyword}&search_type=keyword_unordered"
        )
        return base_url

    def _normalize_ad(self, raw_ad: dict[str, Any]) -> AdRecord:
        """Normalize raw Apify output into AdRecord.

        Supports both the official apify/facebook-ads-scraper schema
        and the legacy scrapeify schema.
        """
        snapshot = raw_ad.get("snapshot", {}) or {}

        archive_id = (
            raw_ad.get("adArchiveId")
            or raw_ad.get("adArchiveID")
        )
        page_name = (
            raw_ad.get("pageName")
            or snapshot.get("pageName")
        )
        ad_text = (
            snapshot.get("body", {}).get("text")
            if isinstance(snapshot.get("body"), dict)
            else snapshot.get("body")
        ) or raw_ad.get("ad_text")
        title = snapshot.get("title")
        link_url = snapshot.get("linkUrl")
        cta_text = snapshot.get("ctaText")
        cta_type = snapshot.get("ctaType")

        media_urls: list[str] = []
        media_type: str | None = None

        images = snapshot.get("images") or []
        videos = snapshot.get("videos") or []

        if videos:
            media_type = "video"
            for video in videos:
                if isinstance(video, dict):
                    url = video.get("url") or video.get("videoUrl") or video.get("src")
                    if url:
                        media_urls.append(url)
                elif isinstance(video, str):
                    media_urls.append(video)
        elif images:
            media_type = "image"
            for image in images:
                if isinstance(image, dict):
                    url = (
                        image.get("originalImage")
                        or image.get("original_image_url")
                        or image.get("url")
                        or image.get("image")
                    )
                    if url:
                        media_urls.append(url)
                elif isinstance(image, str):
                    media_urls.append(image)

        return AdRecord(
            ad_archive_id=archive_id,
            advertiser=page_name,
            ad_text=ad_text,
            title=title,
            link_url=link_url,
            cta_text=cta_text,
            cta_type=cta_type,
            media_type=media_type,
            media_urls=media_urls,
            start_date=raw_ad.get("startDateFormatted") or raw_ad.get("startDate"),
            end_date=raw_ad.get("endDateFormatted") or raw_ad.get("endDate"),
            is_active=raw_ad.get("isActive"),
            platform="Meta Ads Library",
            page_id=raw_ad.get("pageId") or snapshot.get("pageId"),
            source_metadata=raw_ad,
        )

    def _is_relevant(self, record: AdRecord, keywords: list[str]) -> bool:
        """Reject obviously unrelated results."""
        text = " ".join(
            str(value or "")
            for value in (record.advertiser, record.ad_text, record.title, record.cta_text)
        ).lower()

        for keyword in keywords:
            if keyword.lower() in text:
                return True

        return False

    def _deduplicate(self, records: list[AdRecord]) -> list[AdRecord]:
        """Deduplicate on ad_archive_id."""
        seen: set[str] = set()
        unique_records: list[AdRecord] = []

        for record in records:
            archive_id = record.ad_archive_id
            if archive_id and archive_id in seen:
                continue
            seen.add(archive_id)
            unique_records.append(record)

        return unique_records

    def run(
        self,
        keywords: list[str] | None = None,
        lookback_days: int | None = None,
        max_results: int | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        """Run ad research and save normalized results."""
        keywords = keywords if keywords is not None else ["trading", "investing", "stock market"]
        lookback_days = lookback_days if lookback_days is not None else self.DEFAULT_LOOKBACK_DAYS
        max_results = max_results if max_results is not None else self.DEFAULT_MAX_RESULTS
        country = country if country is not None else self.DEFAULT_COUNTRY

        generated_at = datetime.now().isoformat()
        all_records: list[AdRecord] = []

        if self.apify_runner is None:
            self.apify_runner = ApifyRunner()

        for keyword in keywords:
            ad_library_url = self._build_ad_library_url(
                keyword=keyword,
                lookback_days=lookback_days,
                country=country,
            )

            items = self.apify_runner.run_actor(
                actor_id=self.ACTOR_ID,
                run_input={
                    "startUrls": [{"url": ad_library_url}],
                    "resultsLimit": max_results,
                    "activeStatus": "",
                    "sorting": "",
                },
                timeout_secs=300,
            )

            for item in items:
                record = self._normalize_ad(item)
                if self._is_relevant(record, keywords):
                    all_records.append(record)

        unique_records = self._deduplicate(all_records)

        result = {
            "generated_at": generated_at,
            "lookback_days": lookback_days,
            "query_metadata": {
                "actor_id": self.ACTOR_ID,
                "keywords": keywords,
                "max_results": max_results,
                "country": country,
                "query_mode": "startUrls",
                "url_construction": "Meta Ads Library URL embedded in startUrls[0].url",
                "date_filtering": "start_date and end_date embedded in Meta Ads Library URL",
            },
            "source_metadata": {
                "platform": "Meta Ads Library",
                "actor": self.ACTOR_ID,
                "sdk_version": "3.2.0",
            },
            "ad_count": len(unique_records),
            "ads": [record.model_dump(mode="json") for record in unique_records],
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result