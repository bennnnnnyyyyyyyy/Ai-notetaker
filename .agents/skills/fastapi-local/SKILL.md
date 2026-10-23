---
name: fastapi-local
description: Implement and verify changes in this project's local FastAPI, SQLite, Playwright, FFmpeg, transcription, and Ollama stack. Use when editing backend routes, schemas, workers, adapters, or local runtime configuration.
---

# Local FastAPI workflow

- Keep API routes in `backend/routers/`, Pydantic models in `backend/schemas/`, persistence in `backend/database.py`, and pipeline behavior in `backend/workers/` or `backend/adapters/`.
- Keep runtime paths under `data/`; never commit databases, recordings, transcripts, reports, browser profiles, or secrets.
- Use `py -3` because PATH is not dependable. Do not require admin privileges or `cmd`.
- Preserve explicit browser visibility and consent. Do not add flags that auto-approve Meet permissions or bypass admission.
- Prefer a fixture or endpoint smoke test before attempting a real meeting.
- After backend edits run `py -3 -m compileall -q backend` and import `backend.main`.
