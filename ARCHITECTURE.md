# Prime Ad Meeting Intelligence — Architecture Plan

> **Version:** 2.0 — Local-First Build  
> **Implementation approach:** AI-assisted development on Windows  
> **Initial deployment:** One existing PC, one Google account  
> **Fixed monthly budget target:** $0  
> **Primary goal:** Automatically capture Google Meet meetings and generate Prime Ad-specific sales-analysis reports  
> **Operating model:** Analysis only — no autonomous task execution  
> **Paid services:** Optional, only if free local methods fail to meet requirements

---

## Environment Snapshot (as inspected)

| Item | Value |
|------|-------|
| OS | Windows 10 Pro |
| CPU | Intel Core i5-6500 @ 3.20 GHz, 4 cores |
| RAM | ~15.7 GB |
| GPU | Intel HD Graphics 530, 1 GB VRAM (integrated — no CUDA) |
| Disk free (C:) | ~17.4 GB |
| Python | 3.13.5 |
| Node | 22.14.0 |

**Constraints:**
- All AI inference runs CPU-only. No GPU acceleration.
- `faster-whisper` base model (~150 MB). Upgrade to `small` if quality requires it.
- Ollama `phi3:mini` (~2.5 GB RAM) for LLM analysis.
- 60-minute transcript analysis may take 5–15 minutes. Acceptable for non-realtime workflow.
- Keep model storage under 5 GB total.

---

## 1. Executive Summary

Build a local Windows application that automatically joins eligible Google Meet meetings, captures the conversation, transcribes it, and generates structured sales-analysis reports based on Prime Ad's approved MAIN.md rules and campaign-specific configuration files.

The application runs on the existing PC. Recordings, transcripts, reports, and the database are stored locally.

The system must not depend on a paid VPS, paid database, paid meeting-bot API, or paid transcription API for its basic workflow.

The architecture is designed so that an external AI API or meeting-capture provider can be added later if local implementation proves insufficient. Those integrations remain optional.

**The first milestone is to prove that the local PC can reliably capture both sides of a Google Meet conversation. If this fails, do not build the rest of the application around an unproven capture method.**

---

## 2. Required Product Behavior

Normal workflow:

1. An authorized user registers a Google Meet URL, campaign, meeting type, opener, and closer.
2. The application launches a visible browser at the scheduled time.
3. The browser joins the meeting using the authorized Google account.
4. Meeting audio is captured via WASAPI loopback (system audio) using FFmpeg.
5. Audio is saved locally.
6. After the meeting ends, the recording is transcribed using `faster-whisper`.
7. The correct campaign configuration is loaded.
8. MAIN.md universal rules and campaign rules are applied.
9. A structured report is generated using Ollama.
10. The report is validated against the Pydantic schema.
11. The completed report is displayed in the local dashboard.

If any step fails, a clear error is shown and any artifacts already generated are preserved.

---

## 3. System Boundaries

```
┌─────────────────────────────────────────────────────┐
│                  LOCAL MACHINE                       │
│                                                     │
│  ┌──────────┐   audio    ┌─────────────┐            │
│  │ Browser  │──loopback─▶│  Recorder   │            │
│  │(Playwright│            │ (FFmpeg +   │            │
│  │+ Chrome) │            │  WASAPI)    │            │
│  └──────────┘            └──────┬──────┘            │
│                                 │ WAV               │
│                          ┌──────▼──────┐            │
│                          │ Transcriber │            │
│                          │(faster-     │            │
│                          │ whisper)    │            │
│                          └──────┬──────┘            │
│                                 │ JSON segments      │
│                          ┌──────▼──────┐            │
│                          │  Analyser   │            │
│                          │  (Ollama /  │            │
│                          │   phi3:mini)│            │
│                          └──────┬──────┘            │
│                                 │ structured report  │
│  ┌──────────────────────────────▼──────────────┐    │
│  │            FastAPI backend  (SQLite)         │    │
│  └──────────────────────────────┬──────────────┘    │
│                                 │ REST / SSE         │
│  ┌──────────────────────────────▼──────────────┐    │
│  │          Local dashboard  (HTML/JS)          │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

No traffic leaves the machine unless the operator explicitly configures an optional paid adapter.

---

## 4. User Roles

| Role | Responsibilities |
|------|----------------|
| **Opener** | Can view authorized meetings and reports; review qualification gaps; understand whether pre-booking information was sufficient |
| **Closer** | Can review meeting reports, objections, unresolved questions, commercial terms, and scorecard evidence |
| **Management** | Can view reports across authorized campaigns; examine performance trends; review qualification quality; identify recurring process gaps |
| **Administrator** | Can manage users, campaign configurations, system settings, access permissions, retention policies, and operational failures |

The initial version should use a small number of explicit roles. Do not build a complex permissions engine until real requirements justify it.

---

## 5. Meeting Types

### 5.1 Sales and Discovery
What the AI must capture:
- Prospect profile and stated needs.
- ICP and qualification assessment.
- Discovery quality (what the closer asked and found).
- Objections and concerns raised.
- Next steps and meeting outcome.

### 5.2 Deal Negotiation
What the AI must capture:
- Commercial terms explicitly discussed (scope, quantities, pricing).
- Objections and unresolved negotiation points.
- Confirmed commitments vs. expressed interest.
- Supported pipeline outcome.

### 5.3 Client Onboarding
What the AI must capture:
- Confirmed requirements and responsibilities.
- Owners, deadlines, and dependencies.
- Outstanding questions.
- Risks and unresolved implementation details.

---

## 6. Component Catalogue

| # | Component | Role | Technology |
|---|-----------|------|------------|
| 1 | **Meeting Watcher** | Polls SQLite for upcoming meetings; triggers capture worker | APScheduler |
| 2 | **Capture Worker** | Launches browser, joins Meet, starts/stops recording | Playwright + subprocess |
| 3 | **Audio Recorder** | Records WASAPI loopback via FFmpeg | FFmpeg `-f dshow` |
| 4 | **Transcription Worker** | WAV → timestamped JSON segments | `faster-whisper` |
| 5 | **Analysis Worker** | 8-stage prompt chain; structured report | Ollama HTTP API |
| 6 | **Report Validator** | Validates report schema; flags missing fields | Pydantic v2 |
| 7 | **FastAPI Backend** | REST + SSE API; owns all DB writes | FastAPI + `aiosqlite` |
| 8 | **Campaign Config Loader** | Loads/validates YAML campaign configs | Pydantic + PyYAML |
| 9 | **Local Dashboard** | Meeting registration, status, transcript, report | Vanilla HTML/CSS/JS |
| 10 | **Provider Adapters** | Abstract base classes for future paid providers | Python ABCs |

---

## 7. Directory Structure

```
Ai-notetaker/
├── MAIN.md                        # Codex implementation contract
├── ARCHITECTURE.md                # This file
├── README.md
├── .gitignore
├── .env.example
│
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings from .env
│   ├── database.py                # SQLite setup, migrations
│   ├── models/
│   │   ├── meeting.py
│   │   ├── report.py
│   │   └── campaign.py
│   ├── schemas/
│   │   ├── meeting.py             # Pydantic request/response schemas
│   │   ├── report.py
│   │   └── campaign.py
│   ├── routers/
│   │   ├── meetings.py
│   │   ├── reports.py
│   │   └── campaigns.py
│   ├── workers/
│   │   ├── capture.py             # Playwright + FFmpeg orchestration
│   │   ├── transcribe.py          # faster-whisper wrapper
│   │   ├── analyse.py             # Ollama 8-stage prompt chain
│   │   └── watcher.py             # Polling scheduler
│   ├── adapters/
│   │   ├── base_capture.py        # Abstract capture adapter
│   │   ├── base_transcriber.py    # Abstract transcription adapter
│   │   └── base_llm.py            # Abstract LLM adapter
│   └── campaigns/
│       ├── universal_rules.yaml
│       └── example_campaign.yaml
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── tests/
│   ├── test_capture.py
│   ├── test_transcribe.py
│   ├── test_analyse.py
│   └── test_report_schema.py
│
├── data/                          # EXCLUDED from Git
│   ├── recordings/
│   ├── transcripts/
│   ├── reports/
│   └── logs/
│
└── requirements.txt
```

---

## 8. Audio Capture Strategy

### Problem
Playwright controls the browser DOM but cannot directly capture audio output. Google Meet audio plays through the Windows audio stack.

### Solution — WASAPI Loopback via FFmpeg

FFmpeg's DirectShow (`dshow`) input with a loopback device captures everything playing through the system speakers — both sides of the call:

```bash
# Step 1: enumerate available audio devices
ffmpeg -list_devices true -f dshow -i dummy

# Step 2: record loopback
ffmpeg -f dshow -i audio="CABLE Output (VB-Audio Virtual Cable)" \
       -ar 16000 -ac 1 \
       data/recordings/<meeting_id>.wav
```

**Prerequisite:** Install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (free) **or** enable "Stereo Mix" in Windows Sound settings if the driver exposes it. This is a one-time machine setup step — not a paid dependency.

**Fallback:** If neither is available, document the exact blocker and stop. Do not fake a successful recording.

### Browser Audio Routing
Playwright launches Chrome with the user's existing named browser profile so Google Meet grants admission under the authorized account. No cookies or credentials are extracted or committed.

---

## 9. Bot Lifecycle States

The application maintains these normalized status values:

```
scheduled → joining → waiting_for_admission → recording → meeting_ended
                                                              ↓
                                                          processing
                                                              ↓
                                                     completed | failed | cancelled
```

**The application must handle:**
- Meeting links that are invalid.
- Bot waiting to be admitted (waiting room).
- Bot denied entry — record the failure, do not retry unauthorized access.
- Meetings that never start.
- Capture failures mid-recording.
- Duplicate processing triggers.

State transitions must be validated. A completed report cannot regress to `recording` because a delayed event arrived.

---

## 10. Transcript Format

All transcription output normalizes into a common internal format:

```json
{
  "meeting_id": "uuid",
  "model_used": "faster-whisper/base",
  "segments": [
    {
      "segment_id": "seg_001",
      "start_ms": 12500,
      "end_ms": 18300,
      "speaker_id": "speaker_1",
      "text": "We are currently looking for outbound sales support."
    }
  ]
}
```

**Speaker IDs are not automatically employee identities.** The application must not assume `speaker_1` is the closer. Use known meeting participant configuration and mark uncertain attribution explicitly.

Speaker diarisation is **not included** in the baseline. If it becomes a priority, `pyannote.audio` can be added later (requires a free HuggingFace token).

---

## 11. AI Analysis Pipeline — 8 Stages

The analysis worker runs these stages sequentially. Never collapse them into a single unstructured prompt.

### Stage 1 — Transcript Quality
Identify: missing sections, unclear speakers, audio gaps, overlapping speech, other limitations.

### Stage 2 — Fact Extraction
Extract and timestamp-reference:
- Prospect identity and role.
- Business profile.
- Stated needs and current process.
- Pain points.
- Authority and decision process.
- Objections.
- Commercial terms.
- Explicit commitments.
- Dates, owners, and deadlines.
- Unresolved questions.

Each extracted fact retains its transcript segment ID as evidence.

### Stage 3 — Qualification Assessment
Apply universal qualification rules and the active campaign configuration. Produce one of:
- `Confirmed fit`
- `Potential fit — unconfirmed`
- `Outside ICP`
- `Insufficient information`

### Stage 4 — Opener Assessment
Compare what was established before booking against what the closer discovers during the call. Do not penalize the opener for information that was genuinely unavailable before the meeting.

**Opener scorecard categories (1–5):**
| Category | Description |
|----------|-------------|
| Booking quality | Was the right type of prospect booked? |
| Information accuracy | Was pre-booking information correct? |
| Expectation setting | Were prospect expectations set correctly? |
| Pre-meeting capture | Was relevant information recorded before the meeting? |

### Stage 5 — Closer Scorecard
Score each category 1–5 with transcript evidence. Use **"Not assessable"** if evidence is insufficient.

| Category | Description |
|----------|-------------|
| Discovery | Did the closer understand the prospect's real needs? |
| Presentation | Did the closer explain the relevant service clearly? |
| Objection handling | Did the closer address concerns raised? |
| Qualification | Did the closer establish need, readiness, and commitment? |
| Closing effectiveness | Did the closer ask for the sale or secure a specific second meeting? |

Also assess:
- Conversation control.
- Whether material prospect questions were answered.

Do not infer quality solely from the deal outcome.

### Stage 6 — Outcome Assessment
Identify the supported meeting outcome and pipeline stage.

**Allowed outcomes:**
- Closed / purchase committed
- Qualified opportunity — second meeting booked (specific date and time confirmed)
- Interested — no confirmed next meeting
- Follow-up required (e.g. contract or documents to be sent)
- Unqualified
- Lost or declined
- Inconclusive — insufficient evidence

Do not advance the deal stage merely because the prospect expressed interest. A proposed next step is not an accepted next step.

### Stage 7 — Report Consolidation
Generate the final report from the extracted evidence and intermediate assessments. Every field that cannot be established is marked `"unknown"`, `"unresolved"`, or `"not_assessable"`. Never fabricate details.

### Stage 8 — Schema Validation
Validate the report against the Pydantic schema and evidence-reference rules before marking it complete. If validation fails, retry a limited number of times or mark the report for human review. Never silently accept malformed output.

---

## 12. Evidence Model

Every finding distinguishes its evidence type:

| Label | Meaning |
|-------|---------|
| `Confirmed fact` | Verifiable from the transcript |
| `Prospect statement` | Said by the prospect |
| `Prime Ad statement` | Said by a Prime Ad representative |
| `AI assessment` | Inferred by the LLM |
| `Explicit commitment` | Agreed to in the meeting |
| `Unknown` | Not established |
| `Unresolved` | Raised but not resolved |

**Key rules:**
- Interest is not a commitment.
- A proposed next step is not an accepted next step.
- A second meeting is confirmed only when a specific date and time are agreed upon.
- Commercial terms are recorded only when discussed — no ROI calculation.
- Uncertain speaker identity must be stated, never invented.

---

## 13. Required Report Sections

Every completed analysis includes:

1. Meeting overview
2. Executive summary
3. Prospect profile
4. ICP and qualification assessment (table: met / unmet / unknown per criterion)
5. Opener performance (scorecard + evidence)
6. Closer performance scorecard (scorecard + evidence)
7. Conversation control and unanswered questions
8. Objections and unresolved issues
9. Commercial terms discussed
10. Outcome and pipeline stage
11. Agreed actions, owners, and deadlines
12. Management observations
13. CRM-ready record for manual use

---

## 14. Campaign Configuration System

### File Layout

```
backend/campaigns/
├── universal_rules.yaml       # Permanent rules applied to every meeting
├── cgm_healthcare.yaml        # Campaign-specific criteria
└── example_campaign.yaml      # Template for new campaigns
```

### Example Campaign YAML

```yaml
campaign_id: example_campaign
name: Example Campaign
version: "1.0"

meeting_types:
  - discovery
  - negotiation
  - onboarding

qualification:
  requirements:
    - id: suitable_business
      description: Business could realistically use the service
    - id: relevant_need
      description: Prospect has a relevant need
    - id: authority
      description: Decision-maker or access to one
    - id: paid_service_interest
      description: Willingness to discuss a paid service
  disqualifiers:
    - id: example_disqualifier
      description: Describe the disqualifying condition

services:
  - name: Example Service
    terminology:
      - term: "Key term"
        definition: "What it means in this campaign"

report:
  use_universal_scorecard: true
  require_evidence: true
  allow_not_assessable: true
```

**Versioning:** Every campaign configuration has a version identifier. Every report retains the exact config version used. A new version applies to future analyses; historical reports retain their original version.

---

## 15. Data Model (SQLite)

### `meetings`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| url | TEXT | Google Meet URL |
| campaign_id | TEXT FK | |
| meeting_type | TEXT | `discovery` `negotiation` `onboarding` |
| opener_name | TEXT | |
| closer_name | TEXT | |
| scheduled_at | DATETIME | UTC |
| status | TEXT | `pending` `joining` `waiting_for_admission` `recording` `meeting_ended` `processing` `completed` `failed` `cancelled` |
| pre_booking_notes | TEXT | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### `recordings`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| meeting_id | TEXT FK | |
| file_path | TEXT | Relative path under `data/recordings/` |
| duration_seconds | REAL | |
| captured_at | DATETIME | |
| error | TEXT | NULL if clean |

### `transcripts`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| meeting_id | TEXT FK | |
| file_path | TEXT | JSON file path |
| model_used | TEXT | e.g. `faster-whisper/base` |
| created_at | DATETIME | |

### `transcript_segments`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| transcript_id | TEXT FK | |
| segment_id | TEXT | e.g. `seg_001` |
| start_ms | INTEGER | |
| end_ms | INTEGER | |
| speaker_id | TEXT | |
| text | TEXT | |

### `reports`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| meeting_id | TEXT FK | |
| version | INTEGER | Increments on regeneration |
| campaign_config_version | TEXT | |
| file_path | TEXT | JSON report path |
| status | TEXT | `draft` `validated` `reviewed` |
| created_at | DATETIME | |

### `campaigns`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| name | TEXT | |
| config_path | TEXT | YAML file path |
| config_version | TEXT | |
| active | BOOLEAN | |

### `report_reviews`
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | |
| report_id | TEXT FK | |
| reviewer | TEXT | |
| feedback | TEXT | |
| corrections_json | TEXT | |
| created_at | DATETIME | |

---

## 16. API Design (FastAPI)

All endpoints under `/api/v1`.

### Meeting Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/meetings` | Register a meeting |
| GET | `/meetings` | List meetings |
| GET | `/meetings/{id}` | Meeting detail and status |
| POST | `/meetings/{id}/start-capture` | Trigger capture worker |
| POST | `/meetings/{id}/retry` | Retry a failed meeting |

### Report Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/meetings/{id}/report` | Get current report |
| POST | `/meetings/{id}/analyze` | Start analysis |
| POST | `/reports/{id}/review` | Save human review/corrections |

### Campaign Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/campaigns` | List campaigns |
| GET | `/campaigns/{id}` | Campaign detail |
| POST | `/campaigns` | Create campaign |

### Status Stream
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/meetings/{id}/status-stream` | SSE stream for live status updates |

---

## 17. Transcription Model Selection

| Model | Size | RAM | WER (en) | CPU speed |
|-------|------|-----|----------|-----------|
| `base` | ~150 MB | ~1 GB | ~15% | ~1× realtime |
| `small` | ~460 MB | ~2 GB | ~10% | ~0.5× realtime |
| `medium` | ~1.5 GB | ~5 GB | ~8% | ~0.25× realtime |

**Default:** `base`. Upgrade to `small` only if quality is demonstrably insufficient.

---

## 18. LLM Model Selection (CPU-only)

| Model | RAM | Tok/s (CPU) | Notes |
|-------|-----|-------------|-------|
| `phi3:mini` | ~2.5 GB | ~4–8 tok/s | **Recommended default** |
| `gemma2:2b` | ~2 GB | ~5–9 tok/s | Alternative if phi3 underperforms |
| `mistral:7b` | ~5–6 GB | ~1–2 tok/s | Avoid — too slow on this CPU |

Long transcripts are chunked (≤ 3,000 tokens). Evidence is consolidated across chunks before generating the final report.

---

## 19. Provider Adapter Pattern

Every external concern has an abstract base class:

```python
# adapters/base_transcriber.py
from abc import ABC, abstractmethod

class BaseTranscriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> list[dict]: ...

# adapters/base_llm.py
class BaseLLMAdapter(ABC):
    @abstractmethod
    def generate(self, system: str, user: str) -> str: ...

# adapters/base_capture.py
class BaseCaptureAdapter(ABC):
    @abstractmethod
    def start(self, meeting_url: str) -> str: ...  # returns recording path
    @abstractmethod
    def stop(self) -> float: ...  # returns duration
```

Concrete implementations: `FasterWhisperTranscriber`, `OllamaLLMAdapter`, `PlaywrightCaptureAdapter`. Swapping providers requires only changing the concrete class in `config.py`.

---

## 20. Security and Privacy

- `data/` directory is in `.gitignore`. Never committed.
- `.env` is in `.gitignore`. `.env.example` is committed as a template.
- Browser profile path is in `.env`, not hardcoded.
- Dashboard is `localhost` only. Never exposed publicly.
- No recording is uploaded anywhere by default.
- Recordings and reports: configurable TTL, safe-delete UI in dashboard.
- The bot must be visible to meeting participants. No hidden capture.
- Healthcare-related discussions: do not process PHI until applicable compliance requirements are reviewed.

---

## 21. Testing Plan

### Capture Tests
- Valid meeting URL
- Invalid URL
- Bot waiting for admission (waiting room)
- Bot denied admission → record failure, do not retry
- Meeting ends early
- Capture fails mid-recording

### Transcript Tests
- Clear audio
- Poor audio
- Overlapping speakers
- Relevant campaign terminology
- Names and numbers
- Missing speaker identity

### Analysis Tests (using reviewed transcripts with known outcomes)
- Confirmed qualification
- Potential qualification
- Outside ICP
- Insufficient information
- Missing decision-making authority
- Unclear need
- Explicit pricing discussed
- Objection not resolved
- Proposed next step — not accepted
- Follow-up agreed without a specific time
- Follow-up agreed with a specific date and time
- Opener lacked pre-booking information
- Closer did not answer a material question
- Campaign configuration missing
- Transcript evidence contradicts initial assessment

### Proposed Pilot Thresholds
| Metric | Target |
|--------|--------|
| Successful capture rate | ≥ 95% of eligible meetings |
| Capture → usable report rate | ≥ 95% |
| Qualification classification agreement with reviewer | ≥ 90% |
| Correctness of explicit dates, owners, commercial terms | ≥ 95% |
| Fabricated confirmed commitments in acceptance set | 0 |

These are targets, not assumed results. If not met, document the failure categories and improve before wider rollout.

---

## 22. Milestone Sequence

| Milestone | Goal | Done when |
|-----------|------|-----------|
| **M1** | Capture PoC | Real WAV saved; both audio sides audible; no paid API |
| **M2** | Transcription | Timestamped JSON from real recording; model chosen and quality verified |
| **M3** | Analysis | Validated report JSON from local LLM; all 8 stages run; schema passes |
| **M4** | Dashboard | Register meeting → view transcript → view report in browser |
| **M5** | Reliability | Retries, dedup, logs, tests, retention controls |

Each milestone must be working and tested before the next begins.

---

## 23. Optional Future Additions (not in scope for initial build)

| Addition | Trigger condition |
|----------|------------------|
| Paid transcription adapter (OpenAI Whisper API) | Local quality demonstrably insufficient |
| Paid LLM adapter (OpenAI GPT-4o) | Local inference too slow or reports inadequate |
| Paid capture adapter (Recall.ai @ $0.50/hr) | Local browser capture proves unreliable |
| Speaker diarisation (pyannote.audio) | Attribution accuracy becomes a priority |
| Google Calendar integration | Auto-discover eligible meetings |
| CRM export (read-only) | Explicit approval |
| PHI compliance review | Before processing any healthcare patient data |
| Multi-tenant commercial product | After successful internal pilot |

All optional additions require explicit approval and must not affect the zero-cost default path.

---

## 24. Repository Constraints

- Never commit `data/`, `.env`, browser profiles, API keys, recordings, or transcripts.
- `.env.example` lists all required variable names with placeholder values — committed.
- `data/` is gitignored at the root level.
- All absolute paths come from `.env` or `config.py` — never hardcoded.
