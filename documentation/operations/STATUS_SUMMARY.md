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
- A full eight-stage Ollama run was attempted against the persisted 45-second transcript. It exceeded the 300-second request timeout during final consolidation after approximately 13 minutes, so no report was accepted as successful. Hosted analysis is now being evaluated as an optional fallback; no provider is configured yet.
- Whisper and Ollama work moved off the FastAPI event loop.
- Pydantic report schema validation.
- Generalized report normalization for meetings without a saved campaign.
- Evidence-gated scorecard repair: numeric scores without criterion-specific evidence and rationale become `Not assessable`.
- Transcript-backed commercial-term extraction records value, fee type/payment timing, status, and segment ID.
- Legacy nested prospect profiles, serialized conversation-control output, action references, and objection references are normalized safely.

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
- Fourteen backend tests pass, including deterministic report-quality regression tests.
- Local readiness endpoint reports ready.

## Verified live processing

- A real authorized Meet recording was captured and persisted: meeting `1bd6a8ba-9951-4c2e-859b-6e8bcf91f4f1`, 21:09 WAV, 153 transcript segments, and a validated Gemini report.
- The existing RPM-style report fixture validates through the current normalization path without a campaign. Repaired output identifies the explicit `$50` one-time fee, `$10` monthly fee, and seven-day payment timing as discussed/proposed terms rather than confirmed commitments.
- Speaker diarization remains unavailable, so no participant identity is inferred.
- Deterministic report v4 for the live RPM meeting is persisted and API-retrievable; it preserves v1–v3 and marks the three commercial terms as proposed/discussed rather than accepted.

## Not yet verified

- A second independent real meeting capture has not yet been validated.
- The eight-stage analysis pipeline remains intentionally unrun for this milestone.
- Phase 2A local admin security boundary is implemented: protected API routes, server-side sessions, CSRF checks, rate-limited login, logout, and audit events. No public tunnel or remote deployment is enabled.
- Phase 2A hardening now fails closed for non-loopback/public configuration without explicit HTTPS and secure cookies, redacts local paths from readiness responses, sanitizes user-facing worker/integration errors, and derives review identity from the authenticated session. Those security checks are included in the current 14-test suite.
- Ollama model availability and full CPU processing time remain unverified.
- A bounded local Ollama call previously returned in 70.84 seconds, but that does not prove the full pipeline is usable.
- Speaker diarization is not implemented.
- Public deployment remains blocked pending a real HTTPS boundary, trusted proxy policy, shared/durable rate limiting, durable jobs, and supervised remote-access testing.
- The report API returns v4 correctly, but the current dashboard detail view does not yet render report contents; only meeting controls and Google Sheets export are shown.
- The dashboard has now been redesigned with an admin-console visual system and meeting-detail report rendering. A user/operator surface is present in the frontend, but separate backend user roles are not yet implemented.
- Added a read-only BD Meetings booking browser for the Desktop `BD MEETINGS 2026.xlsx` workbook. It previews `New Meetings` rows and only permits import when a direct Google Meet URL exists; current sampled rows contain Calendar event-edit links or plain meeting times.

## Next action: report review and supervised follow-up

1. Review the repaired report for the live RPM meeting and mark any business corrections through the review endpoint.
2. For another capture, close every normal Chrome window and end remaining Chrome processes in Task Manager.
3. Start the server:

   ```powershell
   py -3 -m uvicorn backend.main:app
   ```

4. Open `http://127.0.0.1:8000` in Edge.
5. Open the existing failed meeting and click **Start capture**.
6. Confirm a visible Chrome capture tab opens on the Meet URL, not `about:blank`.
7. Manually authenticate if needed, join the authorized meeting, and approve all prompts.
8. Confirm the dashboard changes from `joining` to `recording`.
9. Run the test for 30–60 seconds, then close the visible capture browser.
10. Verify the WAV file is non-zero and inspect the meeting status.

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
