# Backend Audit — 2026-10-26

Scope: FastAPI routes, SQLite lifecycle, capture/transcription/analysis workers, local adapters, configuration, and diagnostics. This audit is based on static inspection plus local endpoint/import checks. It does not claim a successful real Google Meet capture.

## Health Summary

| Area | Score | Finding |
|---|---:|---|
| API correctness | 2/4 | Core routes work, but capture start is race-prone and input validation is weak. |
| Capture reliability | 1/4 | FFmpeg starts, but browser/profile navigation and lifecycle failures can leave ambiguous states. |
| Pipeline reliability | 2/4 | Errors are persisted, but CPU transcription and synchronous HTTP analysis run inside async workers. |
| Data safety | 2/4 | Local paths and SQLite are appropriate for the prototype, but path and recording validation are incomplete. |
| Observability | 2/4 | Logging exists, but FFmpeg diagnostics are discarded and status transitions are not consistently exposed. |
| **Total** | **9/20** | **Poor for unattended operation; acceptable only as a supervised prototype.** |

## Executive Summary

- Local checks passed: backend compilation, application import, `/health`, readiness, campaign listing, and meeting listing.
- No automated test files are currently present; `pytest` reports “no tests ran”.
- The immediate capture path is the priority. The backend can start FFmpeg and launch a visible browser, but a real Meet navigation/join/capture cycle is not yet verified.
- Issues found: **2 P0, 4 P1, 4 P2**.

## Critical Findings

### [P0] Capture startup can leave a zero-byte recording and an unclear live state

- **Location:** `backend/adapters/playwright_capture.py:42-131`, `backend/workers/capture.py:58-95`
- **Impact:** FFmpeg starts before browser launch/navigation is proven. If browser startup or navigation fails, a zero-byte or partial WAV can remain and the meeting can appear stuck in `joining` until the worker finishes.
- **Recommendation:** Validate the browser launch/navigation first where practical, capture FFmpeg stderr to a per-meeting log, verify process health and non-zero output before inserting a recording record, and always record a terminal failure reason.

### [P0] Capture depends on a live Chrome profile lock and is not isolated

- **Location:** `backend/adapters/playwright_capture.py:84-107`, `backend/config.py:55-75`
- **Impact:** Any background Chrome process can prevent startup or cause the automated browser to close. This has already blocked the user’s real test.
- **Recommendation:** Use a dedicated, user-created browser profile reserved for capture, or add a supported connect-to-an-existing-browser workflow. Keep the current profile approach clearly marked as supervised-only.

### [P1] Duplicate capture jobs can be scheduled concurrently

- **Location:** `backend/routers/meetings.py:67-85`
- **Impact:** Two clicks or repeated requests can enqueue multiple workers before the first worker updates the database, causing competing browsers, FFmpeg processes, and conflicting status updates.
- **Recommendation:** Atomically transition `pending`/`failed` to `joining` in the API before enqueueing, and reject any second start while a worker is active.

### [P1] Meeting URL input is not constrained to authorized Google Meet URLs

- **Location:** `backend/schemas/meeting.py:5-14`, `backend/adapters/playwright_capture.py:115`
- **Impact:** The API accepts arbitrary strings and the browser adapter will attempt to navigate to them. That is unsafe for a local automation tool and can produce confusing failures.
- **Recommendation:** Validate with `HttpUrl`, require `https`, and restrict the hostname to an approved Google Meet host pattern before capture starts.

### [P1] CPU-bound transcription blocks the async application

- **Location:** `backend/workers/transcribe.py:40-47`, `backend/workers/capture.py:86`
- **Impact:** `faster-whisper` runs synchronously inside an async background task. During transcription, readiness/status requests may become unresponsive on this four-core CPU.
- **Recommendation:** Run transcription in a worker thread/process or separate job process and expose processing progress independently from the HTTP event loop.

### [P1] Synchronous Ollama calls block analysis and have no cancellation boundary

- **Location:** `backend/adapters/ollama_llm.py:39-51`, `backend/workers/analyse.py:106-145`
- **Impact:** Multiple five-minute synchronous HTTP calls run inside async analysis. A slow local model can make the server appear frozen and can leave a meeting in `processing` for a long time.
- **Recommendation:** Use an async HTTP client or move the entire analysis job off the event loop, with per-stage timeouts and resumable stage state.

### [P2] FFmpeg stderr is discarded

- **Location:** `backend/adapters/playwright_capture.py:65-70`
- **Impact:** Device, permission, and codec errors are hidden. Diagnosing an empty recording requires reproducing the command manually.
- **Recommendation:** Write bounded stderr to `data/logs/<meeting_id>.ffmpeg.log` and include the final relevant error in `error_message`.

### [P2] Status transitions are incomplete and partly inferred from browser closure

- **Location:** `backend/workers/capture.py:61-84`, `backend/adapters/playwright_capture.py:166-172`
- **Impact:** The database has `waiting_for_admission`, but the adapter never sets it. Closing the browser is treated as meeting end even when it may represent a startup failure.
- **Recommendation:** Define explicit lifecycle signals for browser launched, Meet loaded, waiting for admission, recording, and user-ended capture.

### [P2] Campaign and file-path inputs are insufficiently constrained

- **Location:** `backend/routers/campaigns.py:32-48`, `backend/routers/reports.py:20-32`, `backend/workers/analyse.py:85-96`
- **Impact:** Campaign creation accepts arbitrary config paths, and report loading trusts paths stored in SQLite. This is unsuitable beyond a trusted local operator.
- **Recommendation:** Restrict campaign files to the project campaign directory and resolve/validate paths before reading.

### [P2] No automated backend test suite exists

- **Location:** repository test scan; `pytest -q` returned no tests.
- **Impact:** Capture lifecycle regressions can reach the user without a repeatable test covering startup failure, retry, cleanup, and status transitions.
- **Recommendation:** Add unit tests for routers, diagnostics, worker state transitions, and adapter failure cleanup; add one local fake-browser/ fake-FFmpeg integration test.

## Positive Findings

- SQLite uses foreign keys and WAL mode, and data directories are created at startup.
- Capture cleanup attempts to stop FFmpeg and close Playwright in both normal and error paths.
- Runtime data is kept under ignored `data/` paths, and the project instructions explicitly exclude credentials, browser profiles, recordings, and transcripts from Git.
- The readiness endpoint accurately checks local Python, FFmpeg, audio device, and profile prerequisites without starting a recording.
- The analysis schema uses Pydantic validation and the prompts explicitly prohibit fabricated facts.
- The app passed local import/compile checks and basic TestClient endpoint checks.

## Recommended Order

1. Stabilize supervised capture: dedicated profile, navigation timeout, FFmpeg log capture, non-zero recording validation.
2. Make capture start atomic and prevent duplicate workers.
3. Add strict Meet URL validation.
4. Move Whisper and Ollama work off the async event loop.
5. Add automated tests around the complete capture lifecycle.

This report is a review record, not evidence that a real meeting was captured successfully.
