# AI Notetaker — Current Status Summary

Updated: 2026-10-26

## Objective

Build a local-first Read AI-style meeting intelligence prototype for authorized Google Meet sessions.

The intended flow is:

```text
Register meeting → open visible Meet browser → manually join/consent
→ capture both-sided audio → stop when meeting ends
→ transcribe locally → analyze against campaign rules → save report
```

The initial prototype must use the existing PC, local storage, free/local tools, and no paid APIs or hosted meeting-bot service.

## Completed

### Project structure and documentation

- Added maintainable project instructions in `AGENTS.md`.
- Added separated documentation areas for architecture, plans, operations, reviews, planning, and campaign references.
- Added project-local workflow, FastAPI, and validation skills.
- Added campaign source documents and matching YAML configurations for DME, CGM, and Roofing.

### Backend and data flow

- FastAPI application with SQLite persistence.
- Meeting, campaign, report, review, readiness, and status endpoints.
- Local data directories for recordings, transcripts, reports, and logs.
- Startup recovery for meetings interrupted by a server stop.
- Atomic capture/retry claiming to prevent duplicate capture workers.
- HTTPS Google Meet URL validation.
- Campaign configuration path restrictions.

### Capture setup

- Playwright installed.
- Installed Google Chrome is selected automatically for the configured authorized profile.
- FFmpeg Essentials installed locally with DirectShow support.
- `CABLE Output (VB-Audio Virtual Cable)` detected by FFmpeg.
- FFmpeg per-meeting logs enabled.
- Zero-byte recordings rejected.
- Browser startup, navigation, cleanup, and partial-capture handling improved.
- Capture now creates a dedicated visible browser tab instead of relying on Chrome’s startup tab.

### Local processing

- faster-whisper CPU transcription adapter; a 45-second CPU benchmark produced timestamped segments in 17.21 seconds cold / 10.46 seconds warm, with a measured 457.6 MB peak process working set. The normal worker now persists transcripts and stops before analysis.
- Ollama analysis adapter.
- Eight-stage evidence-based report pipeline.
- Whisper and Ollama work moved off the FastAPI event loop.
- Pydantic report schema validation.

### Dashboard

- Meeting registration and campaign selection.
- Local capture readiness display.
- Live status refresh during active processing.
- Accessible status/error regions and keyboard focus styles.
- Responsive layout for narrow screens.
- Local system font fallback and tokenized status colors.

### Verification

- Backend compilation passes.
- FastAPI import passes.
- Frontend JavaScript syntax check passes.
- Three backend tests pass.
- Local readiness endpoint reports ready.

## Not yet verified

- No successful real Google Meet capture has been completed yet.
- No real meeting audio has been confirmed in a saved WAV file.
- No full-length production transcript or analysis report has been validated from a meeting. The isolated 45-second real-recording test is persisted and verified.
- The eight-stage analysis pipeline remains intentionally unrun for this milestone.
- Phase 2A local admin security boundary is implemented: protected API routes, server-side sessions, CSRF checks, rate-limited login, logout, and audit events. No public tunnel or remote deployment is enabled.
- Ollama model availability and full CPU processing time remain unverified.
- Speaker diarization is not implemented.

## Next action: supervised capture test

1. Close every normal Chrome window and end remaining Chrome processes in Task Manager.
2. Start the server:

   ```powershell
   py -3 -m uvicorn backend.main:app
   ```

3. Open `http://127.0.0.1:8000` in Edge.
4. Open the existing failed meeting and click **Start capture**.
5. Confirm a visible Chrome capture tab opens on the Meet URL, not `about:blank`.
6. Manually authenticate if needed, join the authorized meeting, and approve all prompts.
7. Confirm the dashboard changes from `joining` to `recording`.
8. Run the test for 30–60 seconds, then close the visible capture browser.
9. Verify the WAV file is non-zero and inspect the meeting status.

If the browser still opens blank, preserve the server output and inspect:

```text
data/logs/<meeting-id>.ffmpeg.log
```

Do not claim capture success until the saved file is non-zero and the authorized test is manually confirmed.

## After capture succeeds

1. Run a short fixture transcription test with the saved WAV.
2. Confirm the local Whisper model is usable on this CPU.
3. Confirm Ollama and `phi3:mini` are installed and responsive.
4. Generate one report using a campaign whose qualification criteria have been approved.
5. Add the real capture result and processing timings to the worklog.
