# Reliability Plan — make capture dependable on this PC

Status: proposed 2026-11-06. Based on `documentation/reviews/PC_AND_PIPELINE_AUDIT_2026-11-06.md`.
Goal: every authorised call produces a usable recording, and the operator learns within a minute if it will not.

Work is in priority order. Items marked **[code]** can be done in this repository. **[owner]** needs a decision or a Windows setting that only the user can make. **[approval]** is a data change or external action that needs explicit approval first.

## Phase A — Stop losing calls (audio)

| # | Type | Change | Done when |
|---|---|---|---|
| A1 | code | **DONE 2026-11-06 (visual warning only; the alert sound is still to do).** **Live silence watchdog.** While recording, measure the level of the growing WAV every 10–15 s. If nothing above about −60 dB arrives for 60 s after admission, set a `warning` on the meeting, show a red banner on the dashboard and play a local alert sound. Keep recording. | A test feeding a silent fake WAV raises the warning; a test with tone does not. |
| A2 | code | **Pre-flight sound check** in readiness: play a short tone to the default output with the bundled `ffplay` while capturing 2 s from `CABLE Output`, then report "audio reaches the cable: yes/no". | Readiness shows a pass/fail for real signal, not just whether the device exists. |
| A3 | owner | **Hear what is being recorded.** Windows Sound → Recording → CABLE Output → Listen → "Listen to this device" → headset. No admin needed. The operator then hears exactly what is captured and notices silence immediately. | Operator confirms they hear the call through the cable. |
| A4 | owner + code | **Route only the bot's browser to the cable** so the headset can stay the default output. Windows "App volume and device preferences" routes by program, so capture must use a different program from the operator's Chrome (Playwright Chromium or Chrome Beta). First test whether Google sign-in works in that browser. | A capture works with the headset as the Windows default output. |
| A5 | code | **Protect recordings.** After capture and after transcription, check the WAV still exists and record its size in the database. Report a missing file as an error instead of silently continuing. | A test removing the file produces a visible error. |
| A6 | approval | Mark the four existing silent "completed" meetings as failed. Flag report `787f636e_v1` as built on a 3-line transcript. Look for the missing `6a89d9a5` WAV (Recycle Bin, sync tools, antivirus quarantine). | Database matches reality. |

## Phase B — Make the weak PC cope

| # | Type | Change |
|---|---|---|
| B1 | owner | Reduce the operator's Chrome: it holds 11.9 GB in 95 processes. Turn on Chrome Memory Saver and close unused tabs/windows before scheduled calls. This is the single biggest free improvement. |
| B2 | code | **Job queue.** Do not transcribe inside the capture worker. Queue transcription and run it only when no capture is active. Analysis runs from the same queue. |
| B3 | code | Give Whisper 3 CPU threads (`cpu_threads=3`) so capture always has one core free. Then compare `base` vs `small` accuracy on the known-good `1bd6a8ba` recording before changing the model. |
| B4 | code | Readiness blocks capture when C: has under 2 GB free. Optionally compress older recordings to FLAC after transcription, which is lossless and smaller. |
| B5 | owner | Free disk space: Downloads (2.9 GB), Desktop (5.9 GB); C: has 7 GB free. Decide a retention period for recordings (B4 can then enforce it). |
| B6 | owner | Hardware, only if wanted: a larger SSD helps most cheaply. A local AI model needs a machine with a recent NVIDIA GPU or Apple Silicon; it could run on another PC on the office network instead of this one. |

## Phase C — Decide where analysis runs

This PC cannot run the current analysis locally. Pick one:

1. **Hosted (current: OpenRouter, free models).** Works today. Call content leaves the PC. Requires a privacy check of the provider's data terms, especially because DME/CGM calls may mention patient information. Update the management email to say so.
2. **Local, simplified.** Install Ollama, use a 3B-class model, cut the pipeline from 8 stages to 2 (extract facts, then write the report), and run it overnight from the B2 queue with Chrome closed. Private and free, with lower report quality; it must be measured on `1bd6a8ba` before relying on it.
3. **Local on a stronger PC on the office network.** Private and fast; needs that machine.

Code work for any option:
- **C1:** remove the duplicate `LLM_PROVIDER` line in `.env` (owner).
- **C2:** add an explicit `ALLOW_EXTERNAL_AI=true` switch. Without it, analysis refuses hosted providers.
- **C3:** show "Analysed by: <service> (external / local)" on each report in the dashboard, using the new `generated_by` field.

## Phase D — Correctness and test debt

| # | Change |
|---|---|
| D1 | Pin `av` to a version compatible with `faster-whisper` 1.1.0 in `requirements.txt` (the installed 19.0.2 crashes its decoder), and test the fallback path. |
| D2 | WAV reader: check sample rate and channel count, and convert with FFmpeg if they are not 16 kHz mono. |
| D3 | Set `asyncio_default_fixture_loop_scope` to remove the test warning. |
| D4 | Verify that the dashboard actually displays report contents (WORKLOG 2026-10-26 says it did not). |
| D5 | Deferred: speaker labels. A single mixed channel needs a diarisation model, which is too heavy for this PC. Revisit if stronger hardware (B6 or Phase C option 3) becomes available. |

## Order

A1 → A3 → A2 → A5 → B2 → B3/B4 → D1/D2 → C (decision) → A4 → the rest. Phase A must be done and one authorised short test call must produce a non-silent recording before more real calls are scheduled.
