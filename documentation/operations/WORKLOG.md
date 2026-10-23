# AI Notetaker Worklog

## 2026-10-23 — Add DME, CGM, and Roofing campaign sources

**Objective.** Convert the provided business rules into maintainable campaign sources and runtime configurations.

**Actions Completed.** Added canonical Markdown sources for DME Lead Generation, CGM Patient Acquisition, and Roofing Appointment Setting. Added matching YAML configs with four qualification criteria each, disqualifiers, evidence requirements, and report rules. Added safe startup seeding for bundled campaigns so they appear in the local dashboard without overwriting existing rows.

**System Result.** The campaign list now has three usable campaign records; analysis can reference their IDs and version `1.0`. The Markdown files remain the human-readable source of truth.

**Safety Status.** Local SQLite metadata only. No external data, meeting content, credentials, or production systems changed.

The previous scaffold campaign `cgm_healthcare` remains in SQLite for old references but is inactive; only the supplied campaign definitions are selectable for new meetings.

## 2026-10-23 — Add capture readiness diagnostics

**Objective.** Continue Milestone 1 by making local capture prerequisites visible and testable without starting a browser or recording.

**Actions Completed.** Added `GET /api/v1/system/readiness`, dashboard readiness rows, async Playwright Chromium detection, FFmpeg resolution, browser-profile checks, and DirectShow audio-device enumeration when FFmpeg is available. Tightened capture startup to detect an FFmpeg process that exits immediately and to clean up the Playwright runtime.

**System Result.** The current machine reports Playwright Chromium ready, but FFmpeg is unavailable, no authorized browser profile is configured, and audio devices cannot yet be enumerated. Capture is correctly reported as `needs_setup`.

**Safety Status.** Read-only diagnostics and local error handling only. No browser was opened, no meeting was joined, and no recording was created.

## 2026-10-23 — Verify local browser components

**Objective.** Install and verify the visible browser component needed by the capture proof of concept.

**Actions Completed.** Installed Playwright Chromium locally. Tested the bundled Playwright FFmpeg helper and confirmed it does not support the DirectShow `-list_devices` option, so the application does not use it for meeting audio.

**System Result.** Visible Chromium is ready. A full FFmpeg build with DirectShow support is still required; the configured VB-Audio device is not currently detected, and no authorized browser profile is configured.

**Safety Status.** No browser session was opened and no meeting or audio was captured.

## 2026-10-23 — Install and verify full FFmpeg

**Objective.** Provide the DirectShow-capable FFmpeg prerequisite without administrator access.

**Actions Completed.** WinGet could not launch because the available `winget.exe` was a broken zero-byte WindowsApps alias pointing at another user. Installed Gyan’s FFmpeg Essentials ZIP locally under the user profile and added a safe user-local resolver fallback.

**System Result.** FFmpeg 9.0.2 Essentials is available and DirectShow enumerates `Microphone (2- Logi USB Headset)`. The configured `CABLE Output (VB-Audio Virtual Cable)` device is not present, so both-sided meeting capture is not ready yet.

**Safety Status.** No meeting was joined and no recording was created. The local download is outside the repository and not committed.

## 2026-10-23 — Add maintainability system

**Objective.** Add a breathable project documentation and agent workflow based on the maintainability conventions used in `dmedesk-prospector`, without copying its application structure.

**Actions Completed.** Added root agent instructions, README and plan discipline; created canonical documentation folders for architecture, plans, operations, planning, reviews, and reference; added a current architecture map, master plan, checklist, and initial review; added three focused project-local skills for workflow, FastAPI work, and post-patch validation.

**System Result.** Future changes have explicit locations for current state, target state, working notes, historical evidence, and reviews.

**Safety Status.** Documentation and local agent guidance only. No production systems, external services, meeting recordings, or credentials changed.
