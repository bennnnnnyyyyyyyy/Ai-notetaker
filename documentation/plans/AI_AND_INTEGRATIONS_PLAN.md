# Implementation Plan: AI Sales Intelligence & Connectors

## 1. System Objective & Goal Alignment

Prime Ad Meeting Intelligence is a zero-cost, local-first meeting observer, note-taker, and sales analyst designed to operate as a local alternative to Read AI or Otter:

```text
[Inbound Booking / Calendar] (Cal.com / Activepieces / Zapier)
              │
              ▼
    [FastAPI Orchestrator]
              │
       ┌──────┴──────┐
       ▼             ▼
[Playwright]    [FFmpeg Loopback]
(Auto-join)     (VB-Audio Cable)
       │             │
       └──────┬──────┘
              ▼
   [Local Audio (.wav)]
              │
              ▼
  [faster-whisper Engine] (Local CPU/GPU)
              │
              ▼
 [Timestamped Segments JSON]
              │
              ▼
 [8-Stage Ollama AI Pipeline] (phi3:mini / llama3.2)
   ├─ 1. Transcript Quality
   ├─ 2. Fact & Evidence Extraction
   ├─ 3. Campaign Qualification (DME / CGM / Roofing)
   ├─ 4. Opener Scorecard
   ├─ 5. Closer Scorecard
   ├─ 6. Deal Outcome & Pipeline Stage
   ├─ 7. Report Consolidation
   └─ 8. Pydantic Schema Validation
              │
       ┌──────┴──────────────┐
       ▼                     ▼
[Dashboard UI]       [Outbound Connectors]
(Review/Transcript)  (Activepieces / Webhooks / CRM)
```

---

## 2. Phase Breakdown

### Phase 1: Capture & Transcription Verification (Current Milestone)
* **Goal**: Confirm end-to-end capture produces a real audio file and generates timestamped text segments.
* **Tasks**:
  1. **Run supervised Meet capture**: Confirm automated popup dismissal, mic/camera mute, and "Join now" click.
  2. **Verify audio routing**: Ensure both host and prospect speech are audible in `data/recordings/<id>.wav`.
  3. **Run faster-whisper**: Run `run_transcription` to convert WAV to segment JSON in `data/transcripts/` and populate `transcript_segments` SQLite table.
  4. **Verify transcript segment schema**: Ensure each segment has `segment_id` (e.g. `seg_0001`), `start_ms`, `end_ms`, and `text`.

### Phase 2: Local AI Sales Intelligence Engine (Milestone 3)
* **Goal**: Execute the 8-stage sales analysis pipeline using local Ollama without external API fees.
* **Tasks**:
  1. **Ollama Model Setup**: Pull `phi3:mini` (or `llama3.2`) locally:
     ```powershell
     ollama pull phi3:mini
     ```
  2. **Sequential 8-Stage Execution**:
     * **Stage 1 (Transcript Quality)**: Flag missing audio or poor quality.
     * **Stage 2 (Fact Extraction)**: Extract prospect pain points, budget, current process, explicit commitments with transcript segment references.
     * **Stage 3 (Campaign Qualification)**: Apply campaign rules (`dme_lead_generation.yaml`, `cgm_patient_acquisition.yaml`, `roofing_appointment_setting.yaml`) to output a qualification fit.
     * **Stage 4 (Opener Scorecard)**: Score booking quality, info accuracy, and expectation setting (1–5).
     * **Stage 5 (Closer Scorecard)**: Score discovery, presentation, objection handling, and closing effectiveness (1–5).
     * **Stage 6 (Outcome & Stage)**: Assign definitive outcome (Closed, Qualified, Follow-up, Unqualified, Lost).
     * **Stage 7 (Consolidation)**: Assemble complete JSON report.
     * **Stage 8 (Schema Validation)**: Validate against `Report` Pydantic model.
  3. **Dashboard Report View**:
     * Add report viewer in `frontend/index.html` and `frontend/app.js` displaying:
       - Qualification badges & deal outcome.
       - Opener and Closer scorecards with evidence quotes.
       - Interactive transcript with clickable timestamp navigation.
       - Human review and correction form.

### Phase 3: Connectors & Integrations
* **Goal**: Eliminate manual meeting registration and automate post-call reporting to CRM/workflows.
* **Tasks**:
  1. **Inbound Booking Webhooks (Activepieces / Zapier / Cal.com)**:
     * Add endpoint `POST /api/v1/integrations/booking-webhook`.
     * Receives event payloads from Cal.com, Zapier, or Activepieces when a demo is booked (e.g., DMEDESK).
     * Extracts `meeting_url`, `scheduled_at`, `campaign_id`, `opener_name`, `closer_name`, and `pre_booking_notes`.
     * Automatically registers the meeting in SQLite and schedules capture.
  2. **Google Calendar Auto-Discovery (Optional)**:
     * Read scheduled Google Meet links directly from the user's Google Calendar for the day.
  3. **Outbound Report Dispatcher (Activepieces / CRM Webhook)**:
     * Add configurable webhook dispatch on `meeting.status == 'completed'`.
     * Sends validated report JSON (qualification status, scores, summary, action items) to Activepieces/Zapier.
     * Enables automatic sync to CRM (GoHighLevel, HubSpot, Close) without storing CRM credentials in the local app.

---

## 3. Immediate Next Execution Steps

1. **Pull Ollama model**:
   Execute `ollama pull phi3:mini` so the local analysis engine has its model ready.
2. **Conduct the real Meet test recording**:
   Start capture on a test call, speak 20 seconds, end the meeting, and verify transcript + report generation.
3. **Build the Inbound Webhook Connector**:
   Implement `POST /api/v1/integrations/booking-webhook` so Cal.com and Activepieces can register meetings automatically.
