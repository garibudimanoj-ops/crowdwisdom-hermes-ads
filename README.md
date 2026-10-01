# CrowdWisdomTrading Video Ads Agent

An AI-powered video advertising pipeline built for the CrowdWisdomTrading internship assessment.

The system uses **Hermes Agent Framework, Python, OpenRouter, Apify, Tavily/Exa, and OpenMontage/Remotion** to research successful ads, extract marketing insights, develop ad concepts, create cinematic storyboards, select visual assets, and produce a final short-form video advertisement.

## Final Deliverables

### Cinematic Ad

**45-second vertical video (9:16)** designed as a cinematic movie-style advertisement.

`outputs/videos/final_crowdwisdom_ad.mp4`

### Hermes Technical Demo

**165-second technical walkthrough** showing the complete agent pipeline and generated artifacts.

`outputs/demo/final_demo.mp4`

## Project Pipeline

```text
Apify
  ↓
Ads Manager Agent
  ↓
Marketing Analysis
  ↓
Research Agent
  ↓
CrowdWisdom Data Agent
  ↓
Script Agent
  ↓
Creative Director
  ↓
Cinematography Agent
  ↓
Asset Selection
  ↓
Shot List
  ↓
OpenMontage / Remotion
  ↓
Final Video Ad
```

## Agents

### Ads Manager Agent

Collects recent advertising examples from the Meta Ads Library through Apify.

### Marketing Analyzer

Extracts recurring:

* Marketing angles
* Customer pain points
* Hooks
* Creative concepts
* Positioning patterns

### Research Agent

Uses Tavily or Exa to research the identified audience, pain points, and market context.

### Data Agent

Provides CrowdWisdom-specific creative intelligence used by the script generation stage.

### Script Agent

Generates multiple advertising concepts covering:

1. Pain-point research
2. CrowdWisdom-specific insights
3. How CrowdWisdom helps the target audience
4. Visual hooks

### Creative Director

Reviews the concepts and selects/refines the strongest creative direction.

### Cinematography Agent

Converts the selected concept into a cinematic visual plan containing:

* Scene timing
* Camera direction
* Shot composition
* Lighting
* Visual continuity
* Visual transitions

### Video Agent

Builds the final video production plan and connects the generated shot plan with the video composition workflow.

## Technology Stack

| Technology             | Purpose                                   |
| ---------------------- | ----------------------------------------- |
| Python                 | Agent orchestration and pipeline logic    |
| Hermes                 | Agent framework                           |
| OpenRouter             | LLM generation                            |
| Apify                  | Meta/Facebook Ads Library data collection |
| Tavily / Exa           | Web research                              |
| OpenMontage / Remotion | Video composition                         |
| FFmpeg                 | Video processing                          |
| JSON                   | Intermediate agent artifacts              |

## Generated Artifacts

The pipeline stores inspectable outputs throughout the workflow.

```text
outputs/
├── ads/
├── insights/
├── research/
├── scripts/
├── storyboards/
├── visual_prompts/
├── video_production/
├── videos/
└── demo/
```

Examples include:

* `ads.json`
* `marketing_insights.json`
* `research.json`
* `concept_1.json`
* `concept_2.json`
* `concept_3.json`
* `final_storyboard.json`
* `full_cinematography_plan.json`
* `real_footage_selection.json`
* `shot_list.json`
* `asset_manifest.json`
* `preflight_report.json`
* `pipeline_status.json`

## Configuration

Create a `.env` file using `.env.example`.

```env
APIFY_API_TOKEN=
TAVILY_API_KEY=
EXA_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
```

Do not commit real API keys to GitHub.

## Installation

```powershell
git clone https://github.com/garibudimanoj-ops/crowdwisdom-hermes-ads.git
cd crowdwisdom-hermes-ads

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Configure the required environment variables before running the pipeline.

## Running the Pipeline

The main orchestration code is available in:

```text
src/orchestrator.py
```

The individual agents are implemented under:

```text
src/agents/
```

Validation and supporting scripts are available in the repository root.

## Testing

Run the test suite with:

```powershell
pytest
```

## Video Production

The final cinematic composition was produced using the OpenMontage/Remotion workflow.

The advertisement uses a vertical **9:16** format and a cinematic visual language intended for short-form advertising.

The technical demo is a separate **16:9** presentation showing how the agent pipeline works.

## Compliance

The generated advertisement avoids presenting trading outcomes as guaranteed.

CrowdWisdomTrading is presented as a **research platform**, while trade execution remains under the user's control.

The project does not claim:

* Guaranteed returns
* Guaranteed predictions
* Zero-loss trading
* Financial advice
* Independently audited performance

Company-specific performance information used in the creative pipeline is treated as company-published information rather than independently verified performance.

## Repository Structure

```text
crowdwisdom-hermes-ads/
├── assets/
├── data/
├── docs/
├── outputs/
├── src/
│   ├── agents/
│   ├── integrations/
│   └── orchestrator.py
├── tests/
├── BAS.md
├── PDS.md
├── TSD.md
├── requirements.txt
├── .env.example
└── README.md
```

## Assessment

Built as the **CrowdWisdomTrading Video Ads Agent internship assessment**.

The repository contains the implementation, agent outputs, research artifacts, production planning files, validation scripts, and final video deliverables.
