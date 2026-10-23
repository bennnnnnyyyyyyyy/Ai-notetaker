# MAIN.md — Prime Ad Meeting Intelligence
## Implementation Contract for Codex

---

## 1. Your Role

You are the implementation engineer for Prime Ad Meeting Intelligence.

Build a **local-first, zero-cost** meeting note-taker and sales-analysis application on the existing Windows PC.
The developer is using AI-assisted coding and wants to minimize paid dependencies.

Follow this document as the project's **primary implementation contract.**

Do **not** merely explain what should be built.
Inspect the repository and environment, implement the next defined milestone, run relevant tests, and report the actual results.

Do **not** claim that a feature works unless you have tested it or clearly state that it remains unverified.

---

## 2. Product Objective

Build an application that automatically joins eligible Google Meet meetings, captures audio, transcribes the conversation, and produces evidence-based sales-analysis reports using Prime Ad's universal and campaign-specific rules.

The system is a **meeting observer and analyst only.**

It **must not:**
- Send emails.
- Book meetings.
- Update a CRM.
- Execute external tasks.
- Assign work in other applications.
- Run arbitrary tools through the LLM.
- Make autonomous business decisions.

It **may** record agreed actions, owners, and deadlines in the report.

---

## 3. Absolute Cost Constraint

The initial version must work without paid API credentials.

**Use:**
- The existing Windows PC.
- The existing browser and Google account.
- Playwright for browser automation.
- FFmpeg for audio processing.
- `faster-whisper` for local transcription.
- Ollama for local LLM inference.
- SQLite for structured data.
- Local filesystem storage.
- A local web application (FastAPI + vanilla HTML/CSS/JS).

**Do not add:**
- A paid VPS.
- A managed database subscription.
- A paid meeting-bot API as a required dependency.
- A required OpenAI API key.
- Paid vector databases.
- Paid observability platforms.
- Paid transcription services.

Optional paid adapters may be added later, but the **default configuration must work without them.**

Do not install a large model, add a large dependency, or make destructive environment changes before checking the machine and explaining the need.

---

## 4. Mandatory First Action: Inspect Before Building

Before writing significant code:

1. Inspect the existing repository and working tree.
2. Read the README and existing project instructions.
3. Identify the current branch and uncommitted changes.
4. Check the installed Python version.
5. Check the installed Node.js version, if relevant.
6. Check Windows version.
7. Check RAM, CPU, and GPU availability.
8. Check installed browsers and audio devices.
9. Identify available disk space.
10. Determine which local transcription and LLM options are feasible.

Do **not** overwrite existing work or replace the project structure without a reason.

Produce a short **environment assessment** covering:
- Available hardware.
- Recommended local transcription model.
- Recommended local LLM option.
- Expected resource constraints.
- Any missing prerequisites.

Then begin the first milestone.

---

## 5. Known Environment (verify before acting)

| Item | Value |
|------|-------|
| OS | Windows 10 Pro |
| CPU | Intel Core i5-6500 @ 3.20 GHz, 4 cores |
| RAM | ~15.7 GB |
| GPU | Intel HD Graphics 530, 1 GB VRAM (integrated — **no CUDA**) |
| Disk free (C:) | ~17.4 GB |
| Python | 3.13.5 |
| Node | 22.14.0 |

**Derived constraints:**
- All AI inference runs **CPU-only**. No GPU acceleration.
- Use `faster-whisper` with the `base` model (~150 MB) by default.
- Use Ollama with `phi3:mini` (~2.5 GB RAM) for LLM analysis.
- A 60-minute meeting may take 5–15 minutes to analyse. Acceptable.
- Keep total model storage under 5 GB.

---

## 6. User Roles

| Role | Can do |
|------|--------|
| **Opener** | View authorized meetings and reports; review qualification gaps; understand whether pre-booking information was sufficient |
| **Closer** | Review meeting reports, objections, unresolved questions, commercial terms, and scorecard evidence |
| **Management** | View reports across authorized campaigns; performance trends; qualification quality; recurring process gaps |
| **Administrator** | Manage users, campaign configurations, system settings, access, retention policies, and failures |

The initial version uses a small number of explicit roles. Do not build a complex permissions engine until real requirements justify it.

---

## 7. Meeting Types

### 7.1 Sales and Discovery
The AI must capture:
- Prospect profile and stated needs.
- ICP and qualification assessment.
- Discovery quality (what the closer asked and uncovered).
- Objections and concerns.
- Next steps and meeting outcome.

### 7.2 Deal Negotiation
The AI must capture:
- Commercial terms explicitly discussed (scope, quantities, pricing).
- Objections and unresolved negotiation points.
- Confirmed commitments vs. expressed interest.
- Supported pipeline outcome.

### 7.3 Client Onboarding
The AI must capture:
- Confirmed requirements and responsibilities.
- Owners, deadlines, and dependencies.
- Outstanding questions.
- Risks and unresolved implementation details.

---

## 8. Development Order

Build in this exact order. **Do not start a later milestone before the current one is working and tested.**

### Milestone 1 — Google Meet Capture Proof of Concept

Implement a small, isolated capture prototype.

It should:
- Accept a Google Meet URL.
- Launch a **visible** browser.
- Use an authorized existing browser session.
- Attempt to join a permitted test meeting.
- Handle waiting-room and denied-admission states.
- Capture meeting audio via WASAPI loopback using FFmpeg.
- Save audio to `data/recordings/` as a WAV file.
- Record capture duration and errors.

**Audio capture approach:**
```
# Step 1: enumerate available DirectShow audio devices
ffmpeg -list_devices true -f dshow -i dummy

# Step 2: record loopback
ffmpeg -f dshow -i audio="CABLE Output (VB-Audio Virtual Cable)" \
       -ar 16000 -ac 1 data/recordings/<meeting_id>.wav
```

If neither a virtual cable nor "Stereo Mix" is available, **stop and report the exact blocker.** Do not fake a successful recording.

**Do not:**
- Bypass Google authentication, waiting rooms, recording notices, or access controls.
- Extract or commit browser cookies or authentication secrets.
- Assume Playwright alone captures audio.

---

### Milestone 2 — Local Transcription

After capture is demonstrated:
- Integrate `faster-whisper`.
- Use the `base` model by default.
- Process the test recording.
- Produce timestamped transcript segments as JSON.
- Save to `data/transcripts/`.
- Compare output against the actual audio.
- Report speaker-attribution limitations.

Do not add multiple transcription engines without a demonstrated reason.

---

### Milestone 3 — Local AI Analysis

After transcription works:
- Install Ollama. Pull `phi3:mini`.
- Load universal rules from this document (§§9–15).
- Load the selected campaign configuration (YAML).
- Run the **8-stage analysis pipeline** (§10 below).
- Validate the report against the Pydantic schema before saving.
- Preserve transcript segment ID references in every finding.
- Flag missing information and uncertain speaker attribution.

No external API key required for the baseline workflow.

---

### Milestone 4 — Application Interface

After the capture-to-report pipeline works:
- Build a simple local dashboard served by FastAPI.
- Allow the user to register a meeting URL, campaign, meeting type, opener, and closer.
- Show meeting and processing statuses.
- Display the transcript with segment navigation.
- Display the structured report.
- Allow human review and corrections.
- Provide a safe way to delete recordings and related data.

---

### Milestone 5 — Reliability

Add:
- Safe retries with bounded backoff.
- Duplicate-event handling.
- Descriptive error messages.
- Structured local logs (`data/logs/`).
- Report versioning (increment on regeneration).
- Configuration versioning.
- Configurable data retention and deletion.
- Basic tests for business rules and state transitions.

---

## 9. Architecture Rules

**Preferred stack:**
- Python + FastAPI for backend logic.
- SQLite (`aiosqlite`) for the database.
- Local filesystem for recordings, transcripts, and reports.
- Playwright for browser automation.
- FFmpeg for audio processing.
- `faster-whisper` for transcription.
- Ollama for local LLM inference.
- Vanilla HTML/CSS/JS for the frontend.

**Keep these components separate:**
- Meeting registration.
- Meeting capture.
- Audio processing.
- Transcription.
- Campaign configuration.
- AI analysis.
- Report validation.
- Report storage.
- User interface.

**Provider adapters** — every external concern (capture, transcription, LLM) must have an abstract base class so that a paid provider can be added later without rewriting the application.

---

## 10. AI Analysis Pipeline — 8 Stages

Run these stages sequentially. Never collapse them into a single unstructured prompt.

### Stage 1 — Transcript Quality
Identify: missing sections, unclear speakers, audio gaps, limitations.

### Stage 2 — Fact Extraction
Extract and timestamp-reference:
- Prospect identity and role.
- Business profile.
- Stated needs and current process.
- Pain points.
- Authority and decision process.
- Objections.
- Commercial terms.
- Explicit commitments.
- Dates, owners, and deadlines.
- Unresolved questions.

Each extracted fact retains its transcript segment ID.

### Stage 3 — Qualification Assessment
Apply universal qualification rules and the active campaign configuration. Produce one qualification status (§11).

### Stage 4 — Opener Assessment
Compare what was established before booking against what the closer discovers during the call.

**Opener scorecard (1–5 per category):**
| Category | Description |
|----------|-------------|
| Booking quality | Was the right type of prospect booked? |
| Information accuracy | Was pre-booking information correct? |
| Expectation setting | Were prospect expectations set appropriately? |
| Pre-meeting capture | Was relevant information recorded before the meeting? |

Do not penalize the opener for information that was genuinely unavailable before the meeting.

### Stage 5 — Closer Scorecard
Score each category 1–5 with transcript evidence. Use **"Not assessable"** when evidence is insufficient.

| Category | Description |
|----------|-------------|
| Discovery | Did the closer understand the prospect's real needs? |
| Presentation | Did the closer explain the relevant service clearly? |
| Objection handling | Did the closer address concerns raised? |
| Qualification | Did the closer establish need, readiness, and commitment? |
| Closing effectiveness | Did the closer ask for the sale or secure a specific second meeting? |

Also assess:
- Conversation control.
- Whether material prospect questions were answered.

Do not infer quality solely from the deal outcome.

### Stage 6 — Outcome Assessment
Identify the supported meeting outcome and pipeline stage.

**Allowed outcomes:**
- Closed / purchase committed
- Qualified opportunity — second meeting booked (specific date and time confirmed)
- Interested — no confirmed next meeting
- Follow-up required (e.g. contract or documents to send)
- Unqualified
- Lost or declined
- Inconclusive — insufficient evidence

Do not advance the deal stage merely because the prospect expressed interest.

### Stage 7 — Report Consolidation
Generate the final report from extracted evidence and intermediate assessments. Every field that cannot be established is marked `"unknown"`, `"unresolved"`, or `"not_assessable"`. Never fabricate details.

### Stage 8 — Schema Validation
Validate the report against the Pydantic schema and evidence-reference rules before marking it complete. If validation fails, retry a limited number of times or mark the report for human review. Never silently accept malformed output.

---

## 11. Qualification Rules

The general qualification baseline:

1. Suitable business that could realistically use Prime Ad's services.
2. Relevant business need.
3. Relevant decision-making authority or access to a decision-maker.
4. Willingness to discuss a paid service.

Campaign-specific rules may add requirements or disqualifiers.

**Allowed qualification statuses:**
- `Confirmed fit`
- `Potential fit — unconfirmed`
- `Outside ICP`
- `Insufficient information`

Compare pre-booking information against what the closer learns. Do not blame the opener for information that was unavailable before the meeting.

---

## 12. Pipeline Stages

The meeting pipeline vocabulary is:

```
meeting booked → attended → contract sent → invoice sent → signed → onboarded
```

The application records the meeting outcome and the supported pipeline stage. It does **not** change a stage in any external CRM.

If a prospect attends but is unqualified, record that explicitly rather than falsely advancing the deal.

---

## 13. Required Report Sections

Every completed analysis must include:

1. Meeting overview
2. Executive summary
3. Prospect profile
4. ICP and qualification assessment (table: met / unmet / unknown per criterion)
5. Opener performance (scorecard + evidence)
6. Closer performance scorecard (scorecard + evidence)
7. Conversation control and unanswered questions
8. Objections and unresolved issues
9. Commercial terms discussed
10. Outcome and pipeline stage
11. Agreed actions, owners, and deadlines
12. Management observations
13. CRM-ready record for manual use

If a field cannot be established, explicitly mark it `"unknown"`, `"unresolved"`, or `"not_assessable"`.

**Do not fabricate details to fill the report.**

---

## 14. Evidence Rules

Distinguish evidence types in every report field:

| Label | Meaning |
|-------|---------|
| `Confirmed fact` | Verifiable from the transcript |
| `Prospect statement` | Said by the prospect |
| `Prime Ad statement` | Said by a Prime Ad representative |
| `AI assessment` | Inferred by the LLM |
| `Explicit commitment` | Agreed to in the meeting |
| `Unknown` | Not established |
| `Unresolved` | Raised but not resolved |

**Key rules:**
- Interest is **not** a commitment.
- A proposed next step is **not** an accepted next step.
- A second meeting is confirmed only when a **specific date and time** are agreed upon.
- Commercial terms are recorded only when discussed — no ROI calculation.
- Uncertain speaker identity must be stated, never invented.
- Reference transcript segment IDs wherever possible.

---

## 15. Campaign Rules

Campaign-specific configurations are YAML files in `backend/campaigns/`.

Each campaign file must define:
- Campaign identity and version.
- Services.
- ICP.
- Qualification requirements.
- Disqualifiers.
- Relevant terminology.
- Any campaign-specific reporting rules.

Campaign selection must be **explicit or deterministic.**

If the campaign is unknown, **flag the report for review** rather than guessing.

Store the **exact configuration version** used for every report.

Every report retains the version used at the time of generation. A new campaign version applies to future analyses; it does not silently change historical reports.

---

## 16. Local AI Rules

The LLM is a **report generator, not an autonomous agent.**

It **must not** have access to:
- Shell execution.
- Arbitrary filesystem commands.
- Email or calendar action tools.
- CRM action tools.
- External task execution.

Use **structured output** and validate the result against the Pydantic schema before saving.

For long transcripts, use timestamped chunks (≤ 3,000 tokens). Do **not** exceed the model's context limit or discard relevant information silently.

If local inference is too slow or report quality is inadequate:
1. Measure the failure.
2. Try a smaller or more suitable model.
3. Improve prompt structure and validation.
4. Report the remaining limitation.
5. Propose a paid API **only** as an optional fallback requiring explicit approval.

---

## 17. Recording and Privacy

The capture workflow must remain **visible** and follow applicable consent, recording, and company-policy requirements.

**Do not:**
- Hide the bot to evade participant awareness.
- Bypass admission restrictions.
- Capture meetings the account is not authorized to join.
- Upload recordings to external services without explicit configuration and authorization.

Keep recordings and reports **local by default.**

Provide configurable retention and deletion behavior.

Do **not** process protected health information until applicable compliance requirements have been reviewed. Use non-sensitive test meetings until that review is complete.

---

## 18. Local Storage and Secrets

Store application data **outside** the source code repository.

**Data directories (excluded from Git):**
```
data/recordings/
data/transcripts/
data/reports/
data/logs/
data/app.db
```

**Never commit:**
- API keys or tokens.
- Google credentials.
- Browser cookies or session tokens.
- Private recordings.
- Transcripts containing confidential information.

`.env` is in `.gitignore`. `.env.example` is committed as a template with placeholder names only.

Do **not** expose the local dashboard to the public internet.

---

## 19. Coding Standards

- Use small, reviewable changes.
- Inspect existing files before editing them.
- Do not rewrite working code unnecessarily.
- Use typed request and response schemas (Pydantic v2).
- Validate all external inputs.
- Use database migrations or a versioned schema.
- Add tests for business rules and state transitions.
- Handle errors explicitly.
- Avoid hardcoded absolute paths.
- Avoid unnecessary dependencies.
- Keep configuration separate from code.
- Update documentation when behavior changes.
- Do not create fake integrations or placeholder success responses.

**After each change:**
1. Run relevant tests.
2. Inspect errors.
3. Verify expected behavior.
4. Report what was actually tested.
5. Identify what remains unverified.

---

## 20. Definition of Done — Milestone 1

The first milestone is complete **only** when:

- [ ] The capture prototype launches a visible browser.
- [ ] It attempts to join an authorized test meeting.
- [ ] It handles admission failures without bypassing them.
- [ ] It saves a real WAV audio file to `data/recordings/`.
- [ ] The recording contains audible audio from both sides, **or** limitations are clearly documented.
- [ ] The application reports capture duration and any errors.
- [ ] No paid API is required.
- [ ] No credentials or private recordings are committed to Git.

Do **not** build the complete dashboard before this milestone is done.

---

## 21. How to Report Progress

At the end of each milestone, provide:

- Files created or changed.
- Dependencies installed.
- Commands executed.
- Tests run and their results.
- Actual functionality demonstrated.
- Known limitations.
- Any costs introduced.
- The next recommended step.

Do **not** claim completion based on code generation alone.

---

## 22. Start Here

> **Read MAIN.md and ARCHITECTURE.md completely.**  
> Inspect the existing repository and Windows environment before changing anything.

Our hard constraint is **$0 additional cost** for the initial prototype.

Start with **Milestone 1 only:** determine whether this PC can join an authorized Google Meet session through a visible browser and capture both sides of the meeting into a real local audio file.

Check: installed browser, Python, available audio devices (run `ffmpeg -list_devices true -f dshow -i dummy`), RAM, CPU, GPU, and disk space.

Choose the simplest safe approach. Do not bypass Google authentication, admission controls, or recording consent. Do not extract or commit browser cookies, credentials, or session tokens.

Implement the **smallest testable proof of concept.** Do not build the dashboard or install large AI models yet.

Test the capture path and report exactly:
- What works.
- What failed.
- What still requires a real meeting test.
- What the next step should be.

Keep all recordings and configuration secrets out of Git.

> The first engineering milestone is not a product. It is one reliable end-to-end test:  
> **Google Meet → visible local capture → real local audio file.**  
> Everything else is secondary.
