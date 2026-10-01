# CrowdWisdom Hermes Marketing Agents
## BASE - Project Rules, Context, and Non-Negotiables

This file is the shared context for the coding agent and all project modules.

---

## 1. Project Identity

**Project:** CrowdWisdom Hermes Marketing Agents  
**Brand:** CrowdWisdomTrading  
**Website:** https://crowdwisdomtrading.com  
**Language:** Python  
**Agent Framework:** Hermes  
**LLM:** OpenRouter or NVIDIA NIM  
**Ad Research:** Apify  
**Web Research:** Tavily and/or Exa  
**Video Production:** OpenMontage preferred

---

## 2. Primary Mission

Turn:

`real ad research + real recent research + real CrowdWisdom data`

into:

`high-quality cinematic video advertisement`

through a transparent multi-agent workflow.

---

## 3. Agent Chain

```text
SUPERVISOR
    |
    v
ADS MANAGER
    |
    v
MARKETING ANALYZER
    |
    v
RESEARCH AGENT
    |
    v
DATA AGENT
    |
    v
SCRIPT AGENT
    |
    v
CREATIVE DIRECTOR
    |
    v
VIDEO AGENT
    |
    v
QUALITY AGENT
    |
    v
FINAL VIDEO
```

---

## 4. Non-Negotiable Rules

### Rule 1 - Real integrations

Do not fake Hermes, Apify, Tavily, Exa, or OpenMontage integrations.

### Rule 2 - No fabricated evidence

Never invent:

- CrowdWisdom statistics
- advertiser performance
- customer testimonials
- market numbers
- research sources

### Rule 3 - Preserve provenance

Whenever practical, retain:

- source URL
- source filename
- source ID
- retrieval timestamp
- source field used

### Rule 4 - Video first quality

The final ad must feel intentionally designed for video.

### Rule 5 - Minimal text

Use visuals, narration, sound and editing as primary communication mechanisms.

### Rule 6 - Test before claiming completion

Never say a component is complete until it has been executed or otherwise verified.

### Rule 7 - External APIs must be replaceable

Use adapters so mocks can replace live services in tests.

### Rule 8 - Secrets stay local

Never commit `.env` or API keys.

---

## 5. Creative Standard

The evaluator should experience:

**"This looks like an advertisement/mini-film, not an AI demo."**

Target traits:

- immediate visual curiosity
- strong first 3 seconds
- coherent story
- visual escalation
- strong transition from chaos to clarity
- memorable sound design
- professional music
- restrained branding
- natural CTA

---

## 6. Creative Baseline

Working creative direction:

### THE NOISE

Start with a trader drowning in information.

Visually show:

- conflicting signals
- opinions
- charts
- notifications
- multiple screens
- uncertainty

Then transform that chaos into structured crowd intelligence.

CrowdWisdomTrading should appear as part of the solution, not as a random logo pasted at the end.

This is a creative baseline only. The final script must use the actual research and supplied data.

---

## 7. Data Hierarchy

When sources conflict, prefer:

1. supplied authoritative CrowdWisdom data for CrowdWisdom-specific numbers
2. primary or highly reliable recent external sources
3. other relevant source material
4. model interpretation

Model interpretation must never be disguised as sourced fact.

---

## 8. Required Artifacts

```text
outputs/ads/ads.json
outputs/insights/marketing_insights.json
outputs/research/research.json
outputs/scripts/concept_1.json
outputs/scripts/concept_2.json
outputs/scripts/concept_3.json
outputs/storyboards/final_storyboard.json
outputs/creative_review.json
outputs/videos/final_ad.mp4
outputs/videos/quality_report.json
outputs/run_manifest.json
```

Also maintain:

```text
logs/run.jsonl
data/processed/unique_data.json
data/processed/data_dictionary.json
```

---

## 9. Required Creative Tracks

The Script Agent must produce:

### Track 1
Pain / ICP

### Track 2
Unique data

### Track 3
How CrowdWisdomTrading helps the ICP

The three tracks must be meaningfully different, not three rewrites of the same idea.

---

## 10. Default Settings

```text
LOOKBACK_DAYS=30
TARGET_DURATION_SECONDS=45
MIN_DURATION_SECONDS=30
MAX_DURATION_SECONDS=60
VIDEO_FORMAT=9:16
```

Use conservative external API limits.

---

## 11. Coding Style

Prefer:

- small modules
- typed functions
- Pydantic models
- explicit error handling
- clear names
- reusable adapters
- deterministic file paths
- structured logs
- testable functions

Avoid:

- giant single-file implementations
- hard-coded API keys
- hidden network calls
- duplicated API logic
- unvalidated LLM JSON
- unnecessary dependencies

---

## 12. LLM Prompt Rules

All agent prompts should explicitly tell the model:

- what role it has
- what evidence it receives
- what output schema it must produce
- what it must not invent
- when uncertainty exists

The model must not claim it browsed the web unless the actual tool returned results.

---

## 13. JSON Rules

All persistent structured artifacts must be valid JSON.

LLM-generated JSON must pass schema validation before being saved as a final artifact.

If parsing fails:

1. attempt safe repair
2. revalidate
3. fail clearly if still invalid

Do not silently save malformed JSON.

---

## 14. Run Resumability

Before invoking an expensive operation, check whether the expected artifact already exists.

Example:

```text
ads.json exists -> reuse
research.json exists -> reuse
final_storyboard.json exists -> reuse
```

`--force` may invalidate cached stages.

---

## 15. Demo Mode Rule

Demo mode may simulate external integrations, but it must label them as simulated.

Do not represent fixture data as real collected data.

---

## 16. Human Review Boundary

The system may automate research, synthesis, scripting and video production, but the final creative direction should remain inspectable.

Store the reasoning artifacts as structured files rather than hiding all decisions inside a single opaque model response.

---

## 17. Evaluator Experience

A fresh evaluator should be able to understand the project quickly:

```text
README
   |
   +--> architecture
   +--> setup
   +--> demo
   +--> real run
   +--> output artifacts
   +--> final video
```

The Kanban dashboard should make the agent workflow visible during execution.

---

## 18. Final Submission Context

Expected submission package:

- GitHub/GitLab repository link
- Apify token/configuration details requested by the company
- Tavily token/configuration details requested by the company
- video output of the Hermes Kanban workflow
- final generated advertisement

Never publish those tokens in a public repository. Provide secrets only through the private channel requested by the evaluator.

---

## 19. Coding Agent Instruction

Read these three files before implementing:

1. `BASE.md` - project rules and non-negotiables
2. `PDS.md` - product/design requirements
3. `TSD.md` - technical implementation requirements

Then inspect the current official Hermes and OpenMontage documentation before implementing their adapters.

Implement in phases.

After each phase:

- run tests
- inspect outputs
- fix errors
- update documentation
- continue

Never fabricate successful results.

---

## 20. Final Success Condition

Success means the repository can run a real pipeline that goes from research to a valid, cinematic 30-60 second CrowdWisdomTrading video while preserving evidence, structured artifacts, reproducibility, and visible agent progress.
