# PC and Pipeline Audit — 2026-11-06

Scope: this PC's capacity to run capture, transcription and analysis, and why most captures produced no usable transcript. Read-only measurements, plus local Whisper runs on two 60-second excerpts (deleted afterwards). No meeting was joined, nothing was recorded, and no external service was called.

## 1. The machine

| Item | Measured | Effect |
|---|---|---|
| CPU | Intel i5-6500, 4 cores / 4 threads, 93% load during audit | No spare cores while the operator's Chrome is busy |
| RAM | 15.7 GB total, **1.4 GB free** | Chrome alone uses **11.9 GB in 95 processes** |
| GPU | Intel HD 530 | No GPU acceleration for Whisper or a local AI model |
| Disk C: | 128 GB Samsung PM830 SATA SSD, **7 GB free** | Recordings are about 1.9 MB per minute; models and caches compete for space |
| Ollama | Not installed / not running (`localhost:11434` unreachable, no `~/.ollama`) | Local analysis is currently impossible |

Earlier measurements (WORKLOG 2026-10-26):
- Whisper `base` ran at 0.23–0.38× real time when the CPU was free.
- The 8-stage Ollama `phi3:mini` analysis of a **45-second** clip took about 13 minutes and then timed out.

**Conclusion:** transcription is fine on this PC. Local AI analysis with the current 8-stage pipeline is not. The main day-to-day bottleneck is memory used by the operator's Chrome.

## 2. Why captures failed: audio routing, not Whisper

Loudness of each recording on disk (FFmpeg `volumedetect`, run locally):

| Meeting | Length | Mean level | Transcript | Finding |
|---|---|---|---|---|
| `1bd6a8ba` | 21 min | −23 dB | 153 lines | Good |
| `787f636e` | 19 min | −29 dB overall, but **−108 dB (digital silence) for most 2-minute windows** | 3 lines | Short bursts of sound, otherwise nothing |
| `b05ec058` | 8 min | **−91 dB** | 0 | Digital silence |
| `86dc49f5` | 20 s | **−91 dB** | 0 | Digital silence |
| `7c2d6672` | 22 s | −42 dB | 0 | Near-silent |
| `6a89d9a5` | 23 min | — | 0 | **WAV file missing from disk** (see §4) |

Re-running Whisper on a 60-second excerpt (auto-detected language vs forced English):
- On `1bd6a8ba` it gave identical results either way: 107 words, English, confidence 0.96.
- On `787f636e` it gave 0 words, and only 2 words with the voice filter off.

The English-only setting is **not** the cause. The audio itself is empty.

**Root cause (very likely):** capture records the `CABLE Output` device, which only receives sound while Windows' *default playback device* is `CABLE Input`. Windows currently lists the Logi USB headset under three different names ("Logi", "2- Logi", "3- Logi"). It has reconnected repeatedly, and a reconnecting headset can take over as the default output. When that happens, the bot's audio goes to the headset and the recording is silent. Nothing warns the operator during the call; the failure is only discovered after transcription.

## 3. Correction to the earlier fact check (claim 9a)

The bot records its own speaker output, so it records **everyone else in the meeting**. That includes the operator if they join from their own account or device. What is never recorded is the bot's own microphone, which stays muted. "The user's microphone is not captured" is therefore true only when the operator talks through the bot's session.

## 4. Other findings

| # | Severity | Finding | Evidence |
|---|---|---|---|
| F1 | High | No warning during a silent capture; up to 2 hours of silence are recorded and only flagged afterwards. | `backend/workers/capture.py` (status loop never inspects audio) |
| F2 | High | The 23-minute recording `6a89d9a5` was written (FFmpeg logged 43 MB) and transcribed to 0 lines at 20:02 on 2026-10-27, and is now missing. Nothing in the app's code deletes recordings, so the cause is unknown. | `data/logs/6a89…ffmpeg.log`, database `recordings` row |
| F3 | High | Analysis is set to an external service (OpenRouter). These are DME/CGM healthcare sales calls, and nobody has reviewed what call content may be sent or whether a free tier may keep or train on it. | `.env` `LLM_PROVIDER` (duplicated, lines 18 and 33) |
| F4 | Medium | Installed `av` 19.0.2 is not pinned and is incompatible with `faster-whisper` 1.1.0: the library's own decoder crashes (`unexpected keyword argument 'metadata_errors'`). The app works only because it reads WAV files itself; its fallback path would crash. | `requirements.txt`, `faster_whisper_transcriber.py:51-57` |
| F5 | Medium | The WAV reader assumes 16 kHz mono 16-bit without checking. Any other WAV would give wrong timestamps or garbage. | `faster_whisper_transcriber.py:52-54` |
| F6 | Medium | Transcription runs inside the capture worker immediately after a call. With back-to-back meetings it competes for the 4 cores with the next capture. | `capture.py:115-117` |
| F7 | Medium | Readiness checks that the cable device *exists*, not that sound *reaches* it, and does not check free disk space. | `backend/diagnostics.py` |
| F8 | Medium | The 8-stage analysis makes many model calls per meeting (several per chunk); this suits neither a weak CPU nor free-tier rate limits. | `analyse.py:_run_pipeline` |
| F9 | Low | No retention policy; recordings stay forever on a nearly full disk. | No cleanup code |
| F10 | Low | `pytest-asyncio` loop-scope warning on every test run. | Test output |

Fixed on 2026-11-06 (see WORKLOG): Meet link validation, silent transcripts marked failed, refusal to analyse transcripts under 50 words, report provenance, capture-worker tests.
