# Master Plan

The project advances in small, verifiable milestones. Do not build downstream components around an unverified foundation.

## Milestone 1 — Capture Proof of Concept (Current Focus)

Verify that this PC can join an authorized Google Meet session and reliably capture **both sides of the conversation** (microphone + remote participants) into a usable local audio file (`data/recordings/<id>.wav`).

Deliverables:
- Supervised browser join test.
- Audio route verification confirming both local mic and remote audio are captured.
- Zero-byte / missing audio rejection.
- Documented result in worklog.

## Milestone 2 — Local Transcription Pipeline

Prove that local transcription works on this machine (Intel i5-6500 CPU, integrated GPU):
- Run `faster-whisper` on a short test fixture recording before processing full meetings.
- Verify timestamped segment generation and SQLite persistence.
- Report resource usage (CPU time, memory headroom) during CPU inference.

## Milestone 3 — Expert Knowledge Base & Evidence-Based Sales Analysis

Incorporate domain expertise and structured intelligence:
- **Expert Knowledge Base**: A persistent local repository of practical DME/CGM sales rules, qualifying questions, common objections, and closer evaluation criteria informed by real sales experience.
- **Model Evaluation**: Benchmark candidate models (`phi3:mini`, etc.) for output quality and CPU execution time against sample transcripts before locking in a model.
- **8-Stage Evidence-Linked Pipeline**: Strict evidence linking to transcript segment IDs; mark unmentioned facts as `unknown` rather than hallucinating.
- **Pydantic Schema Validation**: Enforce complete report structure.

## Milestone 4 — Local Review & Report Interface

Provide a zero-overhead local interface to review meetings:
- View interactive transcript with timestamp navigation.
- Inspect opener and closer scorecards and campaign qualification badges.
- Edit and save human reviews and corrections to reports.

## Milestone 5 — Deferred External Integrations

Only after the entire local pipeline is proven and stable:
- Inbound booking webhooks (Cal.com, Zapier, Activepieces).
- Outbound CRM report dispatchers.
- No external automated actions (emails, CRM updates, booking) in the baseline version.

## Phase 2 — Secure Admin, Calendar Discovery, and Controlled Operations

The next phase is defined in [`PHASE_2_PLAN.md`](PHASE_2_PLAN.md). It adds an authenticated HTTPS admin surface, read-only shared-calendar discovery, policy-controlled Meet capture, durable jobs, and explicit evidence-based analysis. Calendar visibility may authorize discovery, but Google authentication, admission, and recording consent remain authoritative.
