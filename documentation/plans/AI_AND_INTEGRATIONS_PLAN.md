# Implementation Plan: Capture, Sales Intelligence & Expert Knowledge Base

## 1. System Constraints & Hardware Profile

Before downloading models or implementing complex pipelines, the system hardware was inspected:

| Resource | Specification | Constraint / Implication |
|---|---|---|
| **CPU** | Intel Core i5-6500 @ 3.20 GHz (4 cores, 4 threads) | All local AI inference runs on CPU. Inference speed is resource-bound. |
| **GPU** | Intel HD Graphics 530 (Integrated) | No CUDA / discrete VRAM. GPU acceleration is not available. |
| **RAM** | 15.66 GB Total, **4.93 GB Free** | Models must fit within available free RAM without swapping. |
| **Disk** | 118.6 GB Total, **13.8 GB Free** | Strict storage budget. Large model downloads risk filling disk. |

---

## 2. Refined Milestone Roadmap

```text
[Milestone 1: Capture Proof of Concept]
  Verify two-way audio (host mic + remote participant) via loopback
        │
        ▼
[Milestone 2: Local Transcription Pipeline]
  faster-whisper CPU benchmark with audio fixture & Meet recording
        │
        ▼
[Milestone 3: Expert Knowledge Base & Evidence-Based Sales Intelligence]
  - Persistent Expert Knowledge Base (DME/CGM practical rules & objection playbooks)
  - Model benchmarking on CPU against transcripts
  - 8-stage evidence-linked analysis (strictly grounded in segment IDs)
        │
        ▼
[Milestone 4: Local Review & Correction Dashboard]
  Interactive transcript scrubbing, scorecard inspection, human corrections
        │
        ▼
[Milestone 5: Deferred Integrations (Future Phase)]
  Cal.com, Activepieces, Zapier, and CRM sync — deferred until local workflow is proven
```

---

## 3. Milestone Details

### Milestone 1 — Capture Proof of Concept (Immediate Focus)
* **Goal**: Prove that this PC reliably captures **both** the user's microphone and the remote meeting participants in a real, authorized Google Meet call.
* **Requirements**:
  1. Automated pre-join navigation and join execution (implemented in `playwright_capture.py`).
  2. Audio routing validation: Verify `CABLE Output (VB-Audio Virtual Cable)` loopback records two-way conversation into `data/recordings/<id>.wav`.
  3. Validate audio file: Confirm non-zero duration, valid 16kHz mono WAV headers, and clear speech playback from both parties.
  4. Document the exact findings in `WORKLOG.md`.

### Milestone 2 — Local Transcription Pipeline
* **Goal**: Validate `faster-whisper` on the i5-6500 CPU without crashing or exhausting RAM.
* **Requirements**:
  1. Test against a short audio fixture first before processing full-length calls.
  2. Measure CPU utilization, processing speed (Real-Time Factor), and memory usage for the `base` model.
  3. Verify timestamped segments JSON structure (`segment_id`, `start_ms`, `end_ms`, `text`).
  4. Populate SQLite `transcripts` and `transcript_segments` tables.

### Milestone 3 — Expert Knowledge Base & Sales Analysis
* **Goal**: Build an evidence-based sales intelligence system grounded in practical DME/CGM sales expertise.
* **Components**:
  1. **Expert Knowledge Base (First-Class Feature)**:
     - Local YAML/Markdown knowledge files capturing practical sales experience:
       - DME Lead Generation qualification questions, pain points, and objections.
       - CGM Patient Acquisition eligibility criteria, doctor referral friction, and payer rules.
       - Roofing Appointment Setting homeowner confirmation criteria.
       - Closer red flags and conversation control benchmarks.
     - Influences qualification criteria and scorecard rubrics directly.
  2. **Model Evaluation on CPU**:
     - Do not pre-commit to a single large model.
     - Evaluate lightweight candidates (`phi3:mini`, quantized variants) on the i5-6500 CPU for output quality, prompt adherence, and runtime latency using real transcript segments.
  3. **Strict 8-Stage Pipeline**:
     - Require transcript segment ID citations for every material finding.
     - If a detail was not mentioned, mark as `unknown` or `not_assessable` — strictly no fabrication.
     - Pydantic schema validation.

### Milestone 4 — Local Review & Report Interface
* **Goal**: Provide a clean interface for human oversight.
* **Requirements**:
  1. Transcript playback with clickable segment seeking.
  2. Opener and Closer scorecard review.
  3. Form for human corrections, reviewer notes, and status advancement.

### Milestone 5 — Controlled Google Sheets Export
* **Current scope**: Manual, user-triggered export of a meeting/report row to a chosen Google Sheet.
* OAuth credentials and refresh tokens remain local and Git-ignored.
* No automatic CRM mutations, email, booking, or meeting scheduling are included.
* Inbound booking webhooks and broader CRM synchronization remain deferred until the local workflow is proven reliable.

---

## 4. Current Work State & Truth Report

| Area | Status | Evidence / Notes |
|---|---|---|
| **Hardware Profile** | **Checked** | i5-6500 (4 cores), Intel HD 530 GPU, 4.9 GB free RAM, 13.8 GB free disk space. |
| **Capture Adapter** | **Implemented** | Automated Meet pre-join dismiss, mic/cam mute, "Join now" click, and lifecycle tracking in `backend/adapters/playwright_capture.py`. |
| **Server & Dashboard** | **Running** | FastAPI backend running on `http://127.0.0.1:8000`. Readiness shows all subsystems ready. |
| **Real Meet Two-Way Audio** | **Pending** | Needs supervised test to confirm both microphone and remote participant voices are audible in the generated WAV. |
| **Transcription** | **Pending** | `FasterWhisperTranscriber` code exists; CPU benchmark with real/fixture audio pending. |
| **Local LLM Model** | **Postponed** | No model downloaded yet. Awaiting audio and transcription proof. |
| **External Integrations** | **Deferred** | Scope narrowed to local core product first. |
