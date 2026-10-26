# Current Architecture

## System boundary

```text
Visible browser + authorized Google Meet
              │
              ▼
FastAPI backend (backend/main.py)
  ├─ SQLite database (data/app.db)
  ├─ Playwright + FFmpeg capture adapter
  ├─ faster-whisper transcription adapter
  ├─ Ollama local LLM analysis adapter
  └─ Manual Google Sheets export adapter
              │
              ▼
Static dashboard (frontend/)
```

## Runtime components

| Area | Current implementation | Status |
|---|---|---|
| HTTP API | FastAPI routers under `backend/routers/` | Working locally |
| Persistence | SQLite through `aiosqlite` | Working locally |
| Dashboard | Plain HTML/CSS/JavaScript served by FastAPI | Working locally |
| Browser | Playwright visible browser | Scaffolded; real Meet test pending |
| Audio | FFmpeg DirectShow input configured for a named device | FFmpeg and CABLE device verified; real meeting routing test pending |
| Transcription | faster-whisper CPU `base` model | Implemented; model download on first use |
| Analysis | Ollama `phi3:mini` over localhost HTTP | Implemented; Ollama/model setup pending |

## Data flow

1. Register a meeting through the dashboard/API.
2. Start capture for that meeting.
3. Open the Meet URL in a visible browser and record a local WAV file.
4. Transcribe the recording into `data/transcripts/` and SQLite segments.
5. Run the staged analysis pipeline and save a validated JSON report in `data/reports/`.

## Important current limitations

- The capture adapter opens the browser but does not yet robustly automate the authorized join flow or identify all Meet lifecycle states.
- The system intentionally does not auto-approve browser permissions or bypass admission/consent.
- Speaker diarisation is not implemented; transcript speaker IDs are currently unknown.
- This is a local prototype, not a deployed multi-user service.

For the original detailed design and business requirements, see the root [`ARCHITECTURE.md`](../../ARCHITECTURE.md), [`MAIN.md`](../../MAIN.md), and [`dump.md`](../../dump.md).
