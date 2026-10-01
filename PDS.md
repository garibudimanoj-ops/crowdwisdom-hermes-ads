# CrowdWisdom Hermes Marketing Agents
## PDS - Project Design Specification

**Version:** 1.0  
**Project Type:** Internship Assessment / AI Marketing Automation  
**Primary Language:** Python  
**Agent Framework:** Hermes  
**LLM Provider:** OpenRouter or NVIDIA NIM  
**Research/Data:** Apify + Tavily and/or Exa  
**Video Production:** OpenMontage preferred  
**Target Brand:** CrowdWisdomTrading  
**Target Output:** 30-60 second cinematic video advertisement

---

## 1. Purpose

Build a multi-agent AI marketing production system that researches advertising patterns, identifies customer pain points and ICPs, combines current research with CrowdWisdomTrading's unique data, creates multiple video-ad concepts, and produces a final cinematic advertisement.

The system must demonstrate both:

- practical Python engineering
- agent orchestration
- external API integration
- structured data processing
- creative marketing reasoning
- real video production

The project is not a text-ad generator. The primary creative output is a cinematic 30-60 second video ad.

---

## 2. Business Goal

Help CrowdWisdomTrading generate evidence-informed video-ad concepts and finished videos for traders/investors by combining:

1. current advertising patterns
2. current market/customer research
3. CrowdWisdomTrading's unique data
4. structured AI creative development
5. automated video production

---

## 3. Target Audience

Primary ICP:

- retail traders
- active investors
- people researching market sentiment
- traders exposed to conflicting opinions and information overload
- users looking for structured market intelligence

The final ICP must be refined from actual collected evidence rather than assumed only from the project description.

---

## 4. Core User Journey

A user/operator runs:

`python main.py`

The system then:

1. researches relevant ads
2. stores raw ad data
3. analyzes marketing patterns
4. researches pain points and ICP context
5. reads supplied CrowdWisdomTrading data
6. generates three creative concepts
7. creates a detailed storyboard
8. performs creative review
9. sends the approved storyboard to OpenMontage
10. renders the video
11. validates the video
12. exposes the run through a Kanban dashboard

---

## 5. Required Agents

### 5.1 Ads Manager Agent

Responsibilities:

- search relevant trading/investing ads using Apify
- target recent ads, default lookback 30 days
- normalize ad records
- deduplicate records
- preserve source information
- save machine-readable JSON

Output:

`outputs/ads/ads.json`

### 5.2 Marketing Analyzer Agent

Responsibilities:

- analyze collected ads
- identify hooks
- identify pain points
- identify ICPs
- identify emotional triggers
- identify promises/offers
- identify CTA patterns
- identify visual/creative structures
- identify recurring patterns across advertisements

Output:

`outputs/insights/marketing_insights.json`

### 5.3 Research Agent

Responsibilities:

- search current information related to the identified pain points and ICP
- use Tavily as primary search when configured
- use Exa as fallback/deeper search when configured
- preserve source URLs and publication dates when available
- prioritize the last 30 days as requested by the assessment

Output:

`outputs/research/research.json`

### 5.4 Data Agent

Responsibilities:

- inspect supplied CrowdWisdomTrading data
- support CSV/JSON and other practical formats
- validate and normalize data
- calculate safe summaries
- preserve source references
- prevent unsupported statistics

Outputs:

- `data/processed/unique_data.json`
- `data/processed/data_dictionary.json`

### 5.5 Script Agent

Create three different concepts:

1. Pain/ICP concept
2. Unique-data concept
3. Product-value concept showing how CrowdWisdomTrading can help the ICP

Each concept must include a strong visual hook and production-ready shot structure.

Outputs:

- `outputs/scripts/concept_1.json`
- `outputs/scripts/concept_2.json`
- `outputs/scripts/concept_3.json`

### 5.6 Creative Director Agent

Responsibilities:

- review all three concepts
- identify weaknesses
- improve cinematic potential
- improve first 1-3 seconds
- remove generic marketing language
- preserve evidence-backed claims
- produce the final production storyboard

Output:

`outputs/storyboards/final_storyboard.json`

### 5.7 Video Agent

Responsibilities:

- consume final storyboard
- prepare OpenMontage input
- run the video production pipeline
- monitor production
- capture errors
- return final MP4

Output:

`outputs/videos/final_ad.mp4`

### 5.8 Quality Agent

Responsibilities:

- verify the video exists
- verify duration is 30-60 seconds
- verify resolution/format
- verify audio where required
- verify the render is readable/valid
- verify the storyboard exists
- verify data-backed claims have references

Output:

`outputs/videos/quality_report.json`

---

## 6. Creative Requirements

The final advertisement should feel like a short film, not a presentation.

Desired characteristics:

- visual hook in the first 1-3 seconds
- cinematic lighting
- deliberate camera movement
- realistic or highly coherent visual environments
- emotional progression
- sound design
- music
- strong pacing
- visual continuity
- minimal on-screen text
- natural brand reveal
- natural CTA

Avoid:

- generic text slides
- excessive captions
- generic stock-photo slideshow
- repetitive talking-head shots
- unsupported performance claims
- fake data
- invented testimonials

---

## 7. Example Creative Direction

Working concept: **The Noise**

Potential sequence:

- Opening: extreme close-up of a trader's eye reflecting conflicting market information
- Escalation: multiple screens, opinions, notifications, signals, and noise surround the trader
- Pause: chaos abruptly becomes silent
- Transformation: thousands of opinions become an organized visual network
- Insight: CrowdWisdom intelligence/consensus emerges
- Resolution: trader receives a structured view
- Closing: brand reveal and concise CTA

This is a starting creative direction, not a fixed script. Actual claims and visuals must come from collected evidence and supplied data.

---

## 8. Data Principles

The system must distinguish among:

- scraped data
- current research
- supplied unique data
- model-generated interpretation

Every important factual claim used in a storyboard should be traceable to a source or supplied dataset.

Never invent CrowdWisdomTrading statistics.

Never label an ad "successful" based only on model inference. Preserve whatever objective evidence the source provides.

---

## 9. Outputs

The completed project must generate:

- raw Apify output
- normalized ad JSON
- marketing insights JSON
- research JSON
- unique data JSON
- data dictionary
- three creative concepts
- final storyboard
- creative review
- quality report
- run manifest
- final MP4
- logs
- dashboard state

---

## 10. Dashboard Requirements

Provide a local Kanban-style view showing:

`RESEARCH -> ANALYSIS -> SCRIPT -> CREATIVE REVIEW -> VIDEO -> QUALITY -> COMPLETE`

Each card should show:

- agent
- status
- start time
- completion time
- duration
- output artifact
- current message/error

The dashboard reads from structured logs rather than hard-coded states.

---

## 11. Security Requirements

Never commit:

- `.env`
- API keys
- tokens
- passwords
- private credentials

Provide `.env.example` instead.

Never print secrets to console or logs.

---

## 12. Reproducibility

A clean evaluator environment should be able to:

1. install dependencies
2. configure environment variables
3. configure Apify Actor/input
4. configure OpenMontage path/provider requirements
5. run tests
6. run demo mode
7. run the real pipeline

Required commands:

```bash
python main.py --demo
python main.py
```

Stage commands should also be supported where practical.

---

## 13. Definition of Done

The PDS is satisfied when:

- Hermes is genuinely integrated
- real external integrations exist
- ads are stored as JSON
- marketing insights are generated
- current research is collected
- supplied unique data is consumed
- three concepts are produced
- storyboard JSON is valid
- OpenMontage is integrated
- a real 30-60 second MP4 is generated
- quality checks are automated
- Kanban dashboard works
- tests work without paid APIs
- README explains setup and execution
- secrets are excluded from Git
