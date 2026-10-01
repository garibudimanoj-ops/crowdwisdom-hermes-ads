# Implementation Plan

## Overview

Maps PDS/TSD/BAS requirements to technical implementation, source files, output artifacts, and tests.

---

## Phase 1: Repository Inspection (COMPLETE)

**Requirement:** Read PDS.md, TSD.md, BAS.md; inspect existing code and structure.

**Status:** Done

**Artifacts:**
- `PDS.md` — parsed and understood
- `TSD.md` — parsed and understood
- `BAS.md` — parsed and understood
- `main.py` — inspected (basic Apify runner)
- `src/integrations/hermes_runner.py` — inspected (subprocess wrapper)
- `src/integrations/apify_client.py` — inspected (ApifyClient wrapper)
- `.env.example` — inspected
- `.gitignore` — inspected
- `data/unique_data/` — empty
- `outputs/` — empty
- `tests/` — does not exist

---

## Phase 2: Architecture / Implementation Plan (COMPLETE)

**Requirement:** Create `docs/IMPLEMENTATION_PLAN.md` and `docs/DEVELOPMENT_LOG.md`.

**Status:** Done (this document)

---

## Phase 3: Hermes Wrapper Verification

**Requirement:** Verify `HermesAgentRunner` works via `runner.run(prompt, system_prompt=None)`.

**Source:** `src/integrations/hermes_runner.py`

**Test:**
- Unit test: `tests/unit/test_hermes_runner.py`
- Integration test: `hermes -z "Reply with exactly: HERMES PYTHON TEST OK"`

**Output:** Verified Hermes CLI invocation works.

---

## Phase 4: Apify Adapter Verification

**Requirement:** Implement real Apify adapter with configurable Actor ID, lookback, timeout, retry.

**Source:** `src/integrations/apify_client.py` (exists; needs enhancement)

**Test:**
- Unit test: `tests/unit/test_apify_adapter.py` (mocked)
- Integration test: small real Apify call

**Output:** `outputs/ads/ads.json`

**Status:** COMPLETE

**Details:**
- Updated for Apify SDK 3.2.0 typed `Run` objects
- `timeout_secs` translated to `wait_duration=timedelta(seconds=timeout_secs)`
- `run.get("defaultDatasetId")` changed to `run.default_dataset_id`
- Added `run is None` handling
- 6/6 unit tests pass

---

## Phase 5: Ads Manager Agent

**Requirement:** Research relevant trading/investing ads using Apify, last 30 days, normalize, deduplicate.

**Source:** `src/agents/ads_manager.py`

**Dependencies:** Phase 4 (Apify adapter)

**Output:** `outputs/ads/ads.json`

**Test:** `tests/unit/test_ads_manager.py`

**Status:** COMPLETE

**Details:**
- Uses `adLibraryUrl` parameter (not `keyword` due to hardcoded "nike" bug in Actor)
- URL construction: encodes keyword, adds country, start_date/end_date (lookback days)
- Normalization: extracts ad_archive_id, page_name, ad_text, title, media info, timestamps
- Deduplication: removes duplicate ads by ad_archive_id (keeps first occurrence)
- Relevance validation: checks for keyword match in advertiser, ad_text, title, cta_text
- Output serialization: JSON with generated_at, lookback_days, query_metadata, source_metadata, ad_count, ads
- Error handling: raises AdsManagerError on Apify failures
- Tests: 41 unit tests covering all functionality
- Constructor accepts optional `apify_runner`; defaults lazily created in `run()`

---

## Phase 6: Marketing Analyzer Agent

**Requirement:** Analyze collected ads, extract hooks, pain points, ICP, emotional triggers, CTAs, visual patterns.

**Source:** `src/agents/marketing_analyzer.py`

**Dependencies:** Phase 5 (ads.json)

**Uses:** Hermes for analysis

**Output:** `outputs/insights/marketing_insights.json`

**Test:** `tests/unit/test_marketing_analyzer.py`

---

## Phase 7: Research Agent (Tavily/Exa)

**Requirement:** Search current info about retail traders, information overload, market sentiment.

**Source:** `src/agents/research_agent.py`, `src/tools/tavily_tool.py`, `src/tools/exa_tool.py`

**Dependencies:** Phase 6 (pain/ICP context)

**Output:** `outputs/research/research.json`

**Test:** `tests/unit/test_research_agent.py`

---

## Phase 8: CrowdWisdom Data Agent

**Requirement:** Inspect `data/unique_data/`, normalize, validate, produce `data/processed/unique_data.json` and `data/processed/data_dictionary.json`.

**Source:** `src/agents/data_agent.py`

**Dependencies:** None (data is provided or absent)

**Output:** `data/processed/unique_data.json`, `data/processed/data_dictionary.json`

**Test:** `tests/unit/test_data_agent.py`

**Note:** If `data/unique_data/` is empty, create blocked/missing-data state. Never fabricate.

---

## Phase 9: Pydantic Models and Validation

**Requirement:** Create typed models for AdRecord, MarketingInsight, ResearchItem, ScriptConcept, Scene, Storyboard, QualityReport, PipelineResult.

**Source:** `src/models/ad_models.py`, `src/models/insight_models.py`, `src/models/research_models.py`, `src/models/storyboard_models.py`, `src/models/run_models.py`

**Dependencies:** Phase 5-8 (data structures)

**Output:** Validated JSON schemas

**Test:** `tests/unit/test_models.py`

---

## Phase 10: Script Agent

**Requirement:** Generate three creative concepts (Pain/ICP, Unique-data, Product-value).

**Source:** `src/agents/script_agent.py`

**Dependencies:** Phase 6 (insights), Phase 7 (research), Phase 8 (data), Phase 9 (models)

**Uses:** Hermes for concept generation

**Output:** `outputs/scripts/concept_1.json`, `outputs/scripts/concept_2.json`, `outputs/scripts/concept_3.json`

**Test:** `tests/unit/test_script_agent.py`

---

## Phase 11: Creative Director

**Requirement:** Review three concepts, produce final storyboard satisfying creative constraints.

**Source:** `src/agents/creative_director.py`

**Dependencies:** Phase 10 (three concepts)

**Uses:** Hermes for review

**Output:** `outputs/storyboards/final_storyboard.json`, `outputs/creative_review.json`

**Test:** `tests/unit/test_creative_director.py`

---

## Phase 12: OpenMontage Standalone Test

**Requirement:** Inspect OpenMontage docs, verify pipeline interfaces, run minimal test.

**Source:** `src/tools/openmontage_tool.py`

**Dependencies:** OpenMontage at `C:\AI Projects\OpenMontage`

**Output:** Minimal video render verification

**Test:** `tests/unit/test_openmontage_tool.py`

---

## Phase 13: Video Agent

**Requirement:** Consume final storyboard, produce `outputs/videos/final_ad.mp4`.

**Source:** `src/agents/video_agent.py`

**Dependencies:** Phase 11 (storyboard), Phase 12 (OpenMontage verified)

**Uses:** OpenMontage, FFmpeg, Piper TTS

**Output:** `outputs/videos/final_ad.mp4`

**Test:** `tests/unit/test_video_agent.py`

---

## Phase 14: Quality Agent

**Requirement:** Validate video exists, duration 30-60s, 9:16, valid streams.

**Source:** `src/agents/quality_agent.py`

**Dependencies:** Phase 13 (video)

**Uses:** FFmpeg/ffprobe

**Output:** `outputs/videos/quality_report.json`

**Test:** `tests/unit/test_quality_agent.py`

---

## Phase 15: Supervisor / Orchestrator

**Requirement:** Pipeline controller with stage-level execution, resumability, `--force`, `--dry-run`, `--stage`.

**Source:** `src/orchestration/supervisor.py`, `main.py` (enhanced)

**Dependencies:** All phases complete

**Output:** `outputs/run_manifest.json`, `logs/run.jsonl`

**Test:** `tests/unit/test_supervisor.py`

---

## Phase 16: Full Pipeline

**Requirement:** `python main.py` runs complete pipeline.

**Dependencies:** All phases

**Test:** `tests/unit/test_pipeline.py`

---

## Phase 17: Testing

**Requirement:** Run `pytest`, all unit tests pass or failures documented.

**Source:** `tests/`

**Dependencies:** All phases

**Test:** `pytest`

---

## Phase 18: Security Audit

**Requirement:** Check for credential leakage, unsafe subprocess, insecure paths.

**Source:** All source files

**Dependencies:** All phases

**Test:** Manual + automated security checks

---

## Phase 19: Documentation

**Requirement:** Update README.md, docs/IMPLEMENTATION_PLAN.md, docs/DEVELOPMENT_LOG.md.

**Source:** All artifacts

**Dependencies:** All phases

---

## Phase 20: Final Verification

**Requirement:** All acceptance criteria met.

**Test:** Full pipeline run, quality check, documentation review.

---

## File-to-Artifact Mapping

| Requirement | Source File | Output Artifact | Test |
|---|---|---|---|
| Ads Research | `src/agents/ads_manager.py` | `outputs/ads/ads.json` | `tests/unit/test_ads_manager.py` |
| Marketing Analysis | `src/agents/marketing_analyzer.py` | `outputs/insights/marketing_insights.json` | `tests/unit/test_marketing_analyzer.py` |
| ICP Research | `src/agents/research_agent.py` | `outputs/research/research.json` | `tests/unit/test_research_agent.py` |
| CrowdWisdom Data | `src/agents/data_agent.py` | `data/processed/unique_data.json` | `tests/unit/test_data_agent.py` |
| 3 Concepts | `src/agents/script_agent.py` | `outputs/scripts/concept_*.json` | `tests/unit/test_script_agent.py` |
| Storyboard | `src/agents/creative_director.py` | `outputs/storyboards/final_storyboard.json` | `tests/unit/test_creative_director.py` |
| Video Production | `src/agents/video_agent.py` | `outputs/videos/final_ad.mp4` | `tests/unit/test_video_agent.py` |
| Quality Validation | `src/agents/quality_agent.py` | `outputs/videos/quality_report.json` | `tests/unit/test_quality_agent.py` |
| Orchestration | `src/orchestration/supervisor.py` | `outputs/run_manifest.json` | `tests/unit/test_supervisor.py` |
| Hermes Integration | `src/integrations/hermes_runner.py` | - | `tests/unit/test_hermes_runner.py` |
| Apify Integration | `src/integrations/apify_client.py` | - | `tests/unit/test_apify_adapter.py` |
| Models | `src/models/*.py` | - | `tests/unit/test_models.py` |
| Dashboard | `dashboard/app.py` | Kanban UI | `tests/unit/test_dashboard.py` |

---

## Dependency Graph

```
Phase 3 (Hermes)
    ↓
Phase 4 (Apify) → Phase 5 (Ads Manager) → Phase 6 (Marketing Analyzer)
                                                ↓
Phase 7 (Research) ← Phase 8 (Data Agent) ←──┘
    ↓
Phase 9 (Models)
    ↓
Phase 10 (Script Agent) → Phase 11 (Creative Director)
    ↓
Phase 12 (OpenMontage) → Phase 13 (Video Agent) → Phase 14 (Quality Agent)
    ↓
Phase 15 (Supervisor) → Phase 16 (Full Pipeline) → Phase 17 (Testing)
    ↓
Phase 18 (Security) → Phase 19 (Documentation) → Phase 20 (Final)
```

---

## Technical Constraints

- Python 3.13.12
- Hermes CLI v0.21.4 (subprocess wrapper)
- OpenMontage at `C:\AI Projects\OpenMontage`
- All API keys via `.env`, never committed
- No fabricated data
- All JSON must be schema-validated
- Unit tests must mock external APIs
- Demo mode (`--demo`) works without API keys
- `python main.py --stage <stage>` supported
- `python main.py --dry-run` supported
- `python main.py --force` invalidates cached stages
