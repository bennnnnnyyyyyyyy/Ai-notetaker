# AI Notetaker

Local-first meeting capture and analysis for authorized Google Meet sessions.

## Start here

1. Read [`AGENTS.md`](AGENTS.md).
2. Read the [documentation index](documentation/README.md).
3. Read the [current architecture](documentation/architecture/ARCHITECTURE.md).
4. Check the [master plan](documentation/plans/MASTER_PLAN.md) and [worklog](documentation/operations/WORKLOG.md).

## Current implementation

- `backend/` — FastAPI API, SQLite persistence, capture/transcription/analysis adapters.
- `frontend/` — static local dashboard served by FastAPI.
- `data/` — ignored runtime data: database, recordings, transcripts, reports, and logs.
- `ARCHITECTURE.md`, `MAIN.md`, and `dump.md` — original design material retained as reference while the organized documentation is maintained.

## Local run

```powershell
py -3 -m uvicorn backend.main:app
```

Open `http://127.0.0.1:8000`.

The project is still a prototype. A real capture test requires a visible browser, an authorized signed-in session, explicit consent, FFmpeg, and a working Stereo Mix or VB-Audio device.
# Ai-notetaker
