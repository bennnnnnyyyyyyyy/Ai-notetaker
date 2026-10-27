# Internal AI Notetaker Plan Derived from Reddit Research

Status: Proposed internal roadmap; not an approval to add paid services, cloud processing, public access, or external writes.

## Internal scope

This application is for internal meeting operations, sales-quality review, and management visibility. It is not being planned as a customer-facing product, public SaaS, or general-purpose note-taking platform.

Therefore, the plan prioritizes:

- Reliable internal capture and review.
- Evidence-based sales coaching and qualification analysis.
- Controlled access for authorized internal operators and reviewers.
- Local/private storage and deliberately approved internal exports.
- Operational transparency, correction, retention, and auditability.

It does not prioritize public onboarding, pricing, customer accounts, broad market positioning, or supporting every meeting platform.

## 1. What the dump suggests

The dump is useful as qualitative internal workflow research, not as a technical specification or verified benchmark. The useful signals for this internal tool are:

- Capture meetings without an intrusive bot, including face-to-face conversations.
- Accept an existing recording when live capture is not practical.
- Produce notes that are meaningfully useful, not a lightly edited transcript.
- Support speaker identification and more than English over time.
- Make the meeting easy to navigate through chapters, timestamps, and structured sections.
- Turn notes into follow-up work, while keeping the human in control of external actions.
- Earn trust through privacy, consent, reliability, and transparent status.

The current application already has the right foundation: visible authorized Google Meet capture, local files, SQLite, local transcription, optional local analysis, review UI, and manual export.

## 2. Product direction

Build a private internal meeting intelligence workspace for supervised sales and internal meetings. The core promise should be:

> Capture or import a meeting locally, produce evidence-linked notes, and help a human review the next actions.

The internal tool may support three input paths over time:

1. Scheduled or manually started authorized Google Meet capture.
2. Import of an existing local audio/video recording.
3. A supervised local in-person recording path, only after consent UX and Windows audio-device behavior are verified.

The first release should optimize for trustworthy, reviewable output rather than broad platform coverage or external product polish.

## 3. Roadmap and gates

### Phase A — Product contract and measurement

Define the note-taking contract before adding features.

Deliverables:

- A small consent and privacy statement for live capture and imported recordings.
- A representative, locally stored evaluation set using synthetic or approved recordings.
- Scoring rubric for transcript quality, speaker attribution, summary usefulness, action-item precision, latency, CPU use, and failure recovery.
- Product schemas for transcript segments, chapters, decisions, blockers, action items, unknowns, and reviewer corrections.
- Explicit data-retention and deletion behavior for recordings, transcripts, reports, and temporary files.

Acceptance gate: a short fixture can be processed repeatedly and evaluated against the same rubric without relying on subjective memory.

### Phase B — Reliable input and ingestion

Finish the current Meet capture proof and add a safe upload/import path.

Deliverables:

- Complete supervised two-way Google Meet capture verification.
- Add an authenticated local import endpoint/UI for approved audio/video files.
- Validate file type, duration, size, decodeability, and storage location before creating a processing job.
- Normalize imported audio into the existing transcription format.
- Make jobs resumable and idempotent; prevent duplicate processing and concurrent capture conflicts.
- Show clear states: queued, joining, waiting for admission, recording, importing, processing, completed, failed, and needs review.

Acceptance gate: both a verified Meet recording and an imported fixture reach the same downstream transcript/report contract, with bad or zero-byte input rejected safely.

Scope boundary: no bot provider or public webhook is required for this phase.

### Phase C — Transcript quality and navigation

Make the transcript useful on its own before expanding analysis.

Deliverables:

- Benchmark the current faster-whisper configuration and at least one practical alternative available on this machine.
- Add language detection/configuration and record the detected language and model metadata.
- Add speaker diarisation only after measuring its CPU/RAM cost; preserve `unknown` when attribution is uncertain.
- Generate chapters from time windows and topic transitions, with links to transcript timestamps.
- Add transcript search, filtering, click-to-seek playback, and a compact timeline/chapter view.
- Preserve raw transcript segments and model metadata so reports can be regenerated.

Acceptance gate: reviewers can find a decision or action in a long fixture without reading the entire transcript, and speaker labels are never presented as certain when confidence is low.

### Phase D — Evidence-linked meeting intelligence

Expand analysis beyond a generic summary while keeping the existing local model boundary.

Deliverables:

- Add validated report sections for executive summary, topics/chapters, decisions, blockers, action items, follow-ups, risks, and unknown/not-assessable facts.
- Require every material claim to reference one or more transcript segment IDs.
- Keep domain-specific sales scorecards and the expert knowledge base as configurable local data, not hidden prompt text.
- Benchmark candidate local models for quality, latency, and memory before selecting defaults.
- Retry transient model failures, validate structured output, and retain the failed raw response only in protected local diagnostics when safe.
- Allow a user to rerun one analysis mode without re-recording or retranscribing.

Acceptance gate: malformed output is rejected or repaired through a controlled path; unsupported claims become `unknown`; a reviewer can jump from every finding to its evidence.

### Phase E — Review-first workspace

Turn analysis into a dependable human workflow.

Deliverables:

- Meeting detail page combining recording/player, chapters, transcript, report, evidence links, and audit history.
- Reviewer controls for correcting speakers, editing action items, marking findings accepted/rejected, and adding notes.
- Explicit review status such as draft, needs review, approved, and exported.
- Progress updates through the existing status mechanism; consider SSE only if polling becomes inadequate after measurement.
- Accessible, mobile-tolerant layouts for the most common review actions.

Acceptance gate: a reviewer can correct a report, see what changed, and export only an approved version.

### Phase F — Controlled internal export and follow-up

Make approved notes useful to the internal team without creating unsafe automation.

Deliverables:

- Improve the existing manual Google Sheets export with preview, field mapping, validation, and export audit records.
- Add copy/download formats for Markdown and JSON.
- Add an approval queue for action items and follow-up drafts.
- Keep any internal email, CRM, task-manager, calendar, or booking integration behind explicit approval and feature flags.
- Make every external write idempotent, retryable, auditable, and reversible where the provider supports it.

Acceptance gate: no external mutation occurs from analysis completion alone; the operator sees the exact payload and confirms it.

### Phase G — Optional internal expansion after local proof

Consider these only after the local workflow is reliable and measured:

- Supervised in-person recording with a visible recording/consent state.
- Live transcript updates during capture.
- Additional meeting platforms only where there is a clear internal need and a separately reviewed adapter.
- Whiteboard/image attachment processing.
- Timeline, mind-map, or flowchart projections generated from validated report data.
- Approved CRM/task integrations.

These are extensions, not prerequisites for the core internal workflow.

## 4. Reliability and safety requirements for every phase

- Never bypass Google sign-in, admission, recording consent, or browser permission prompts.
- Keep recordings, transcripts, browser profiles, credentials, and local databases out of Git and public routes.
- Use bounded uploads, bounded API responses, path-safe identifiers, and protected artifact access.
- Treat webhook/event handling as idempotent even if no external webhook is used yet.
- Use timezone-aware timestamps and retain model/configuration versions with derived reports.
- Provide deletion/retention controls before adding more integrations.
- Log structured operational events without logging transcript text, tokens, credentials, or raw private paths.
- Verify every real-world capture, audio, browser, or provider claim through an actual recorded test; documentation alone is not evidence.

## 5. Suggested implementation order for the current repository

1. Close the remaining real Meet capture and audio-routing verification gap.
2. Add fixture-based import and unify import/capture processing jobs.
3. Establish the evaluation set and report schemas.
4. Add chaptering, transcript navigation, and evidence links.
5. Benchmark local analysis models and complete the validated intelligence report.
6. Finish reviewer corrections and approval state.
7. Harden manual export, then evaluate one external integration at a time.

## 6. Explicitly not planned from the dump

- Replacing the current backend with the dump's Node/React/Recall.ai example.
- Adding a paid meeting-bot API or cloud LLM without explicit approval.
- Public ngrok-style webhook exposure or public SaaS deployment.
- Automatic emails, CRM updates, task creation, scheduling, or invitations.
- Customer accounts, public onboarding, pricing, billing, or a general-purpose multi-tenant architecture.
- Claiming multilingual accuracy, diarisation quality, or reliability without local benchmarks.

## 7. Relationship to existing plans

- [Master Plan](MASTER_PLAN.md) remains the authority for the milestone sequence.
- [AI and Integrations Plan](AI_AND_INTEGRATIONS_PLAN.md) remains the authority for the expert knowledge base and sales-analysis details.
- [Phase 2 Plan](PHASE_2_PLAN.md) remains the authority for secure admin, calendar discovery, and controlled operations.
- This document adds product-derived priorities and should be reconciled into those plans before implementation begins.
