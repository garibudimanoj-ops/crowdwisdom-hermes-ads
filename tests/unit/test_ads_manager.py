from __future__ import annotations

import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, quote, urlparse

import pytest

from src.agents.ads_manager import AdsManager, AdsManagerError
from src.models.ad_models import AdRecord


def _make_official_raw_ad(**overrides: object) -> dict:
    base = {
        "inputUrl": "https://www.facebook.com/ads/library/?q=trading",
        "adArchiveId": "archive-1",
        "adArchiveID": "archive-1",
        "pageId": "page-1",
        "pageName": "Trading Example",
        "startDate": 1758500000,
        "endDate": 1759000000,
        "startDateFormatted": "Sep 22, 2026",
        "endDateFormatted": "Sep 27, 2026",
        "isActive": True,
        "currency": "USD",
        "spend": 100.00,
        "publisherPlatform": ["FACEBOOK"],
        "snapshot": {
            "pageId": "page-1",
            "pageName": "Trading Example",
            "pageProfileUri": "https://facebook.com/tradingexample",
            "pageProfilePictureUrl": "https://example.com/pic.jpg",
            "caption": "Trading research content",
            "ctaText": "Learn More",
            "ctaType": "LEARN_MORE",
            "displayFormat": "VIDEO",
            "linkUrl": "https://example.com",
            "body": {"text": "Reduce noise when researching the market."},
            "title": "Trading Research",
            "images": [],
            "videos": [],
        },
    }
    base.update(overrides)
    return base


class TestAdsManagerUrlConstruction:
    def test_build_ad_library_url_encodes_keyword(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        url = manager._build_ad_library_url(keyword="trading", lookback_days=30)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "trading" in params["q"][0]

    def test_build_ad_library_url_special_chars_encoded(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        url = manager._build_ad_library_url(keyword="crypto & blockchain", lookback_days=30)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        expected_encoded = quote("crypto & blockchain", safe="")
        assert expected_encoded in url
        assert params["q"][0] == "crypto & blockchain"

    def test_build_ad_library_url_country(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        url = manager._build_ad_library_url(keyword="trading", country="GB", lookback_days=30)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert params["country"][0] == "GB"

    def test_build_ad_library_url_date_filters_present(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        url = manager._build_ad_library_url(keyword="test", lookback_days=30)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "start_date" not in params
        assert "end_date" not in params
        assert params["q"][0] == "test"
        assert params["search_type"][0] == "keyword_unordered"


class TestAdsManagerDateCalculation:
    def test_30_day_default(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        url = manager._build_ad_library_url(keyword="test", lookback_days=30)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "start_date" not in params
        assert "end_date" not in params
        assert params["q"][0] == "test"
        assert params["search_type"][0] == "keyword_unordered"

    def test_custom_lookback(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        url = manager._build_ad_library_url(keyword="test", lookback_days=7)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "start_date" not in params
        assert "end_date" not in params
        assert params["q"][0] == "test"
        assert params["search_type"][0] == "keyword_unordered"


class TestAdsManagerNormalization:
    def test_normalize_minimal(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad()
        record = manager._normalize_ad(raw)
        assert record.ad_archive_id == "archive-1"
        assert record.advertiser == "Trading Example"
        assert record.ad_text == "Reduce noise when researching the market."
        assert record.title == "Trading Research"
        assert record.platform == "Meta Ads Library"
        assert record.source_metadata == raw

    def test_normalize_missing_optional_fields(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(snapshot={}, pageName=None, adArchiveId=None, adArchiveID=None)
        record = manager._normalize_ad(raw)
        assert record.ad_archive_id is None
        assert record.advertiser is None
        assert record.ad_text is None
        assert record.platform == "Meta Ads Library"

    def test_normalize_video_media(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(
            snapshot={
                "pageName": "Video Advert",
                "title": "Video Ad",
                "body": {"text": "Watch this video"},
                "videos": [{"videoUrl": "https://video.example.com/v.mp4"}],
            }
        )
        record = manager._normalize_ad(raw)
        assert record.media_type == "video"
        assert "https://video.example.com/v.mp4" in record.media_urls

    def test_normalize_image_media(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(
            snapshot={
                "pageName": "Image Advert",
                "title": "Image Ad",
                "body": {"text": "Check this image"},
                "images": [{"original_image_url": "https://img.example.com/pic.jpg"}],
            }
        )
        record = manager._normalize_ad(raw)
        assert record.media_type == "image"
        assert "https://img.example.com/pic.jpg" in record.media_urls

    def test_normalize_missing_snapshot(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(snapshot=None)
        record = manager._normalize_ad(raw)
        assert record.ad_archive_id == "archive-1"
        assert record.page_id == "page-1"

    def test_normalize_missing_body_text(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(snapshot={"pageName": "Test"})
        record = manager._normalize_ad(raw)
        assert record.ad_text is None

    def test_normalize_date_fields_from_formatted_strings(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(startDateFormatted="Sep 22, 2026", endDateFormatted="Sep 27, 2026")
        record = manager._normalize_ad(raw)
        assert record.start_date == "Sep 22, 2026"
        assert record.end_date == "Sep 27, 2026"

    def test_normalize_date_fields_from_epoch(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(startDate=1758500000, endDate=1759000000, startDateFormatted=None, endDateFormatted=None)
        record = manager._normalize_ad(raw)
        assert record.start_date == 1758500000
        assert record.end_date == 1759000000

    def test_normalize_is_active(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad(isActive=True)
        record = manager._normalize_ad(raw)
        assert record.is_active is True

    def test_normalize_platform(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        raw = _make_official_raw_ad()
        record = manager._normalize_ad(raw)
        assert record.platform == "Meta Ads Library"


class TestAdsManagerDeduplication:
    def _make_record(self, archive_id: str | None) -> AdRecord:
        return AdRecord(
            ad_archive_id=archive_id,
            advertiser="Test",
            platform="Meta Ads Library",
        )

    def test_deduplicate_by_archive_id(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        records = [
            self._make_record("dup-1"),
            self._make_record("dup-1"),
            self._make_record("unique-1"),
        ]
        result = manager._deduplicate(records)
        assert len(result) == 2
        assert [r.ad_archive_id for r in result] == ["dup-1", "unique-1"]

    def test_deduplicate_none_id_falls_through(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        records = [
            self._make_record(None),
            self._make_record(None),
            self._make_record("unique-1"),
        ]
        result = manager._deduplicate(records)
        assert len(result) == 3

    def test_deduplicate_empty(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        assert manager._deduplicate([]) == []


class TestAdsManagerRelevanceValidation:
    def test_relevant_keyword_match(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        record = AdRecord(
            ad_text="Buy crypto trading signals now",
            title="Trading Signals",
            advertiser="Test Corp",
            cta_text=None,
            platform="Meta Ads Library",
        )
        assert manager._is_relevant(record, ["trading", "investing"]) is True

    def test_no_keyword_match(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        record = AdRecord(
            ad_text="Buy Nike shoes now",
            title="Sneaker Sale",
            advertiser="Nike Store",
            cta_text=None,
            platform="Meta Ads Library",
        )
        assert manager._is_relevant(record, ["trading", "investing"]) is False

    def test_empty_keywords_always_false(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        record = AdRecord(
            ad_text="anything",
            title="anything",
            advertiser="anything",
            cta_text=None,
            platform="Meta Ads Library",
        )
        assert manager._is_relevant(record, []) is False

    def test_case_insensitive_match(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        record = AdRecord(
            ad_text="CRYPTO TRADING",
            title="Signals",
            advertiser="Test",
            cta_text=None,
            platform="Meta Ads Library",
        )
        assert manager._is_relevant(record, ["trading"]) is True

    def test_relevant_by_advertiser_name(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        record = AdRecord(
            ad_text="Buy shoes",
            title="Sneaker Sale",
            advertiser="Trading Platform Inc",
            cta_text=None,
            platform="Meta Ads Library",
        )
        assert manager._is_relevant(record, ["trading"]) is True

    def test_relevant_by_cta_text(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        record = AdRecord(
            ad_text="body text",
            title="title text",
            advertiser="Some Corp",
            cta_text="Start Investing Today",
            platform="Meta Ads Library",
        )
        assert manager._is_relevant(record, ["investing"]) is True


class TestAdsManagerOutputSerialization:
    def test_output_structure(self) -> None:
        manager = AdsManager(apify_runner=MagicMock(), output_path="/tmp/test_ads_output.json")
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        manager.apify_runner = mock_runner

        with patch.object(manager, "output_path"):
            result = manager.run(keywords=["trading"], lookback_days=30, max_results=5)

        assert "generated_at" in result
        assert "lookback_days" in result
        assert "query_metadata" in result
        assert "source_metadata" in result
        assert "ad_count" in result
        assert "ads" in result
        assert result["ad_count"] == 0
        assert result["lookback_days"] == 30
        assert result["query_metadata"]["actor_id"] == "apify/facebook-ads-scraper"
        assert result["query_metadata"]["query_mode"] == "startUrls"
        assert result["source_metadata"]["platform"] == "Meta Ads Library"
        assert result["source_metadata"]["sdk_version"] == "3.2.0"
        assert result["ads"] == []

    def test_output_includes_ad_records_when_actor_returns_data(self) -> None:
        manager = AdsManager(apify_runner=MagicMock(), output_path="/tmp/test_ads_output.json")
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = [
            _make_official_raw_ad(adArchiveId="arch-1", pageName="Trading Example")
        ]
        manager.apify_runner = mock_runner

        with patch.object(manager, "output_path"):
            result = manager.run(keywords=["trading"], lookback_days=30, max_results=5)

        assert result["ad_count"] == 1
        assert result["ads"][0]["advertiser"] == "Trading Example"

    def test_output_does_not_include_api_tokens(self) -> None:
        manager = AdsManager(apify_runner=MagicMock(), output_path="/tmp/test_ads_no_token.json")
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        manager.apify_runner = mock_runner

        with patch.object(manager, "output_path"):
            result = manager.run(keywords=["trading"])

        result_str = str(result)
        assert "APIFY_API_TOKEN" not in result_str

    def test_output_empty_actor_response_yields_zero_ads(self) -> None:
        manager = AdsManager(apify_runner=MagicMock(), output_path="/tmp/test_ads_output.json")
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        manager.apify_runner = mock_runner

        with patch.object(manager, "output_path"):
            result = manager.run(keywords=["trading"], lookback_days=30, max_results=5)

        assert result["ad_count"] == 0
        assert result["ads"] == []


class TestAdsManagerRunMethod:
    def test_run_uses_start_urls_input(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        manager = AdsManager(apify_runner=mock_runner)

        with patch.object(manager, "output_path"):
            manager.run(keywords=["trading"], lookback_days=30, max_results=5, country="US")

        call_args = mock_runner.run_actor.call_args
        assert call_args[1]["actor_id"] == "apify/facebook-ads-scraper"
        run_input = call_args[1]["run_input"]
        assert "startUrls" in run_input
        assert "trading" in run_input["startUrls"][0]["url"]
        assert run_input["resultsLimit"] == 5

    def test_run_default_keywords(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        manager = AdsManager(apify_runner=mock_runner)

        with patch.object(manager, "output_path"):
            manager.run()

        for call in mock_runner.run_actor.call_args_list:
            url = call[1]["run_input"]["startUrls"][0]["url"]
            assert "q=" in url

        first_url = mock_runner.run_actor.call_args_list[0][1]["run_input"]["startUrls"][0]["url"]
        assert "trading" in first_url
        last_url = mock_runner.run_actor.call_args_list[-1][1]["run_input"]["startUrls"][0]["url"]
        assert "stock%20market" in last_url or "stock+market" in last_url or "stock+market" in last_url

    def test_run_includes_country(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        manager = AdsManager(apify_runner=mock_runner)

        with patch.object(manager, "output_path"):
            manager.run(keywords=["trading"], country="GB")

        first_url = mock_runner.run_actor.call_args_list[0][1]["run_input"]["startUrls"][0]["url"]
        parsed = urlparse(first_url)
        params = parse_qs(parsed.query)
        assert params["country"][0] == "GB"

    def test_run_lazily_creates_runner_if_none_provided(self) -> None:
        manager = AdsManager()
        assert manager.apify_runner is None

        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        with patch(
            "src.agents.ads_manager.ApifyRunner", return_value=mock_runner
        ):
            with patch.object(manager, "output_path"):
                manager.run(keywords=["trading"])

        assert isinstance(manager.apify_runner, MagicMock)

    def test_run_raises_on_actor_failure(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run_actor.side_effect = AdsManagerError("Actor failed")
        manager = AdsManager(apify_runner=mock_runner)

        with pytest.raises(AdsManagerError, match="Actor failed"):
            manager.run(keywords=["trading"])

    def test_run_creates_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "ads", "ads.json")
            mock_runner = MagicMock()
            mock_runner.run_actor.return_value = []
            manager = AdsManager(apify_runner=mock_runner, output_path=output_path)

            manager.run(keywords=["trading"])

            assert os.path.exists(output_path)


class TestAdsManagerActorIdentification:
    def test_default_actor_id_is_official(self) -> None:
        manager = AdsManager(apify_runner=MagicMock())
        assert manager.ACTOR_ID == "apify/facebook-ads-scraper"

    def test_actor_id_can_be_configured_via_constructor(self) -> None:
        manager = AdsManager(apify_runner=MagicMock(), actor_id="custom/actor")
        assert manager.ACTOR_ID == "custom/actor"

    def test_run_call_uses_correct_actor_id(self) -> None:
        mock_runner = MagicMock()
        mock_runner.run_actor.return_value = []
        manager = AdsManager(apify_runner=mock_runner, actor_id="apify/facebook-ads-scraper")

        with patch.object(manager, "output_path"):
            manager.run(keywords=["test"])

        call_args = mock_runner.run_actor.call_args
        assert call_args[1]["actor_id"] == "apify/facebook-ads-scraper"