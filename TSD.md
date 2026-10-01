# CrowdWisdom Hermes Marketing Agents
## TSD - Technical Specification Document

**Version:** 1.0  
**Status:** Base implementation specification

---

## 1. Technical Objective

Implement a modular Python multi-agent system using Hermes to orchestrate:

`Ads Collection -> Marketing Analysis -> Research -> Data Processing -> Script Generation -> Creative Review -> Video Production -> Quality Control`

The design must support real APIs while remaining testable through mocks and demo data.

---

## 2. Technology Stack

### Required

- Python 3.10+
- Hermes Agent framework
- OpenRouter or NVIDIA provider
- Apify
- Tavily and/or Exa
- OpenMontage preferred
- FFmpeg
- Node.js 18+ where required by the video stack

### Supporting Python packages

Use only packages needed by the implementation. Typical candidates:

- python-dotenv
- apify-client
- httpx / requests
- pydantic
- tenacity
- rich
- pytest
- fastapi or equivalent lightweight local dashboard framework

Do not blindly install large dependency sets.

---

## 3. Repository Structure

```text
crowdwisdom-hermes-ads/
|
+-- agents/
|   +-- base_agent.py
|   +-- supervisor.py
|   +-- ads_manager.py
|   +-- marketing_analyzer.py
|   +-- research_agent.py
|   +-- data_agent.py
|   +-- script_agent.py
|   +-- creative_director.py
|   +-- video_agent.py
|   +-- quality_agent.py
|
+-- tools/
|   +-- hermes_client.py
|   +-- apify_tool.py
|   +-- tavily_tool.py
|   +-- exa_tool.py
|   +-- data_tool.py
|   +-- openmontage_tool.py
|   +-- file_tool.py
|
+-- models/
|   +-- ad_models.py
|   +-- insight_models.py
|   +-- research_models.py
|   +-- storyboard_models.py
|   +-- run_models.py
|
+-- data/
|   +-- raw/
|   +-- processed/
|   +-- unique_data/
|
+-- outputs/
|   +-- ads/
|   +-- insights/
|   +-- research/
|   +-- scripts/
|   +-- storyboards/
|   +-- assets/
|   +-- videos/
|
+-- dashboard/
|   +-- app.py
|   +-- templates/
|   +-- static/
|
+-- logs/
+-- tests/
+-- scripts/
+-- docs/
|
+-- main.py
+-- pyproject.toml
+-- requirements.txt
+-- .env.example
+-- .gitignore
+-- README.md
```

---

## 4. Configuration

Environment variables:

```env
OPENROUTER_API_KEY=
APIFY_API_TOKEN=
TAVILY_API_KEY=
EXA_API_KEY=
CROWDWISDOM_URL=https://crowdwisdomtrading.com
OPENMONTAGE_PATH=

MAX_AD_RESULTS=50
MAX_RESEARCH_RESULTS=20
MAX_SEARCH_QUERIES=10
MAX_VIDEO_RETRIES=2
LOOKBACK_DAYS=30
TARGET_DURATION_SECONDS=45
VIDEO_FORMAT=9:16
DRY_RUN=false
```

Names may be adjusted to match implementation, but configuration must remain centralized.

---

## 5. Hermes Integration

Create a reusable Hermes client wrapper.

Responsibilities:

- create configured `AIAgent` instances
- apply system prompts per agent
- expose `chat()` execution
- enforce timeouts/retry behavior where appropriate
- parse structured JSON outputs
- record agent events
- prevent credentials from entering logs

Suggested abstraction:

```python
class HermesAgentRunner:
    def run(self, prompt: str, *, system_prompt: str) -> str:
        ...
```

The specialized agents should depend on this abstraction instead of duplicating initialization.

---

## 6. External Tool Interfaces

### 6.1 Apify

Provide:

```python
class ApifyTool:
    def run_actor(self, actor_id: str, run_input: dict) -> list[dict]:
        ...
```

The configured Actor must be inspected before integration because Actor schemas can change.

Requirements:

- configurable Actor ID
- configurable input
- API timeout
- structured errors
- raw output persistence

---

### 6.2 Tavily

Provide:

```python
class TavilyTool:
    def search(self, query: str, *, days: int = 30) -> list[dict]:
        ...
```

Preserve:

- title
- URL
- content/summary
- publication date when available
- retrieval timestamp

---

### 6.3 Exa

Provide an equivalent adapter.

The research agent should select Tavily or Exa according to configuration and fallback rules.

---

## 7. Data Models

Use Pydantic or an equivalent schema library.

### AdRecord

```text
source
ad_id
advertiser
ad_text
creative_url
landing_page
start_date
end_date
platform
collected_at
```

Missing values should remain null/None rather than fabricated.

### MarketingInsight

```text
hook
pain_point
icp
desire
fear
emotion
promise
mechanism
cta
creative_pattern
visual_pattern
source_ads
```

### ResearchItem

```text
query
title
url
source
published_date
evidence
retrieved_at
```

### StoryboardScene

```text
scene_id
start_seconds
end_seconds
duration_seconds
visual
camera
lighting
environment
subject
action
voiceover
sound_effects
music_direction
transition
on_screen_text
asset_requirements
data_references
```

---

## 8. Ads Pipeline

```text
Ads Manager
    |
    +--> Apify Actor
    |
    +--> raw result
    |
    +--> date filter
    |
    +--> duplicate removal
    |
    +--> normalization
    |
    +--> outputs/ads/ads.json
```

The date filter must use source date fields where available and document fallback behavior when dates are unavailable.

---

## 9. Marketing Analysis Pipeline

```text
ads.json
   |
   v
Hermes Marketing Analyzer
   |
   +-- hooks
   +-- pain
   +-- ICP
   +-- emotional triggers
   +-- promises
   +-- CTAs
   +-- visual patterns
   |
   v
marketing_insights.json
```

The model prompt must instruct the agent to distinguish observed patterns from speculation.

---

## 10. Research Pipeline

```text
marketing_insights
        |
        v
pain/ICP queries
        |
   +----+----+
   |         |
 Tavily     Exa
   |         |
   +----+----+
        |
        v
 research.json
```

Use source metadata and recency limits. Do not summarize an absent source.

---

## 11. Unique Data Pipeline

```text
supplied files
      |
      v
schema inspection
      |
      v
validation
      |
      v
normalization
      |
      v
safe summaries
      |
      v
unique_data.json
```

Every derived statistic should retain the source field(s) used to calculate it.

---

## 12. Script Generation

The Script Agent prompt should require exactly three conceptual tracks:

### Track A
Pain/ICP story.

### Track B
Unique CrowdWisdom data story.

### Track C
Product mechanism/value story.

The model must output valid JSON only or pass its output through a strict parser/repair layer.

---

## 13. Storyboard JSON Contract

Example:

```json
{
  "campaign": "CrowdWisdomTrading",
  "title": "The Noise",
  "duration_seconds": 45,
  "format": "9:16",
  "hook": {
    "first_3_seconds": "...",
    "visual": "..."
  },
  "scenes": [
    {
      "scene_id": 1,
      "start_seconds": 0,
      "end_seconds": 4,
      "duration_seconds": 4,
      "visual": "...",
      "camera": "...",
      "lighting": "...",
      "environment": "...",
      "subject": "...",
      "action": "...",
      "voiceover": "...",
      "sound_effects": [],
      "music_direction": "...",
      "transition": "...",
      "on_screen_text": "",
      "asset_requirements": [],
      "data_references": []
    }
  ],
  "cta": {
    "voiceover": "...",
    "visual": "..."
  }
}
```

---

## 14. Creative Director Logic

The Creative Director should not simply select the first concept.

It should inspect:

- visual hook
- clarity
- emotional progression
- product relevance
- evidence integrity
- cinematic continuity
- sound opportunities
- visual novelty
- CTA integration

It should return an improved final storyboard and a review artifact.

---

## 15. OpenMontage Integration

Use the current official OpenMontage project.

Before coding the adapter:

1. inspect its current README
2. inspect available pipelines
3. inspect current command/API entrypoints
4. inspect provider configuration
5. inspect output directory conventions

Do not assume command names based on old tutorials.

The adapter should isolate OpenMontage-specific details from the rest of the application.

Suggested interface:

```python
class OpenMontageTool:
    def render(self, storyboard_path: str, output_dir: str) -> str:
        ...
```

The real implementation may use a subprocess, project file generation, or another documented mechanism depending on the installed version.

---

## 16. Video Quality Checks

Use `ffprobe`/FFmpeg where possible.

Minimum checks:

- file exists
- MIME/container is valid
- duration 30-60 seconds
- video stream exists
- audio stream exists if expected
- width/height are non-zero
- output can be read without immediate decode failure

Recommended production target:

- 9:16
- 1080x1920 when supported
- ~45 seconds

---

## 17. Logging

Use JSON Lines:

`logs/run.jsonl`

Example event:

```json
{
  "timestamp": "2026-09-24T00:00:00Z",
  "run_id": "abc123",
  "agent": "ads_manager",
  "stage": "research",
  "status": "completed",
  "message": "Collected 42 normalized ads",
  "artifact": "outputs/ads/ads.json"
}
```

Never log secrets.

---

## 18. Run Manifest

Generate:

`outputs/run_manifest.json`

Minimum fields:

```text
run_id
started_at
completed_at
status
agents
input_sources
artifacts
video_path
quality_report
errors
```

---

## 19. CLI Specification

Required:

```bash
python main.py
python main.py --demo
```

Recommended:

```bash
python main.py --stage ads
python main.py --stage analysis
python main.py --stage research
python main.py --stage scripts
python main.py --stage video
python main.py --stage quality
python main.py --force
```

Stages should be resumable.

---

## 20. Testing Strategy

Unit tests must not require live external APIs.

Mock:

- Hermes responses
- Apify responses
- Tavily responses
- Exa responses
- OpenMontage execution

Integration tests should validate:

- JSON schemas
- orchestration order
- artifact paths
- failure recovery
- resumability

---

## 21. Failure Handling

For external calls:

- timeout
- retry with backoff
- clear error message
- bounded retries
- preserve partial artifacts

Fallback example:

`Tavily failure -> Exa research attempt -> clear failure only if both fail`

Video failure must not erase the completed research/script artifacts.

---

## 22. Demo Mode

`python main.py --demo` must work without API keys.

It should use local fixtures in:

`tests/fixtures/`

and demonstrate the entire orchestration path with simulated video generation or a known-safe local render path.

The demo must not pretend that a real external API was called.

---

## 23. Performance / Cost Controls

Implement configurable limits.

Do not issue uncontrolled search or video-generation calls.

Examples:

- max ads
- max research queries
- max search results
- max generation retries
- dry-run mode

---

## 24. Deployment Scope

Initial scope is local execution for evaluator reproducibility.

Do not add cloud deployment unless it materially improves the project and does not threaten the 5-7 day delivery target.

---

## 25. Technical Definition of Done

The implementation is complete when:

- all required modules exist
- static tests pass
- demo mode passes
- real APIs are integrated behind adapters
- data artifacts are generated
- script artifacts are generated
- final storyboard passes schema validation
- OpenMontage adapter is verified against the installed version
- final video is generated in a real run
- quality report passes
- dashboard reflects actual logs
- README is complete
