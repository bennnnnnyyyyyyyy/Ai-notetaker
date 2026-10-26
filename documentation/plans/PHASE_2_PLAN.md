# Phase 2 Plan — Secure Admin Operations, Calendar Discovery, and Meeting Intelligence

Status: In progress — Phase 2A local security boundary implemented; public deployment remains unapproved and untested

## 1. Phase 2 objective

Turn the local Phase 1 prototype into a controlled internal application that can be reached through a secure internet-facing admin URL, discover authorized meetings from a shared Google Calendar, start supervised Meet capture through an authorized browser profile, process the recording locally, and expose evidence-backed reports.

Phase 2 is not a plan to bypass Google authentication, Meet admission, meeting restrictions, recording consent, or organizational policy.

## 2. Non-negotiable rules

- Public access requires HTTPS, authentication, authorization, session protection, and an audit trail.
- No anonymous admin page, default credentials, public SQLite file, public recordings, or exposed browser profile.
- Calendar access is read-only in the first release and limited to explicitly selected calendars.
- A calendar event or shared calendar can authorize discovery of a meeting URL; it does not guarantee admission to the Meet.
- If the authorized account is not an attendee, the browser may navigate to the Meet URL and use the normal Google flow, but the result may be `needs_admission` until a host admits it.
- No automatic “Ask to join” approval, host impersonation, cookie extraction, credential extraction, or admission bypass.
- Recording starts only after the configured consent/policy condition is satisfied.
- Audio, transcripts, reports, and credentials remain private by default.
- No paid API, hosting, or subscription is added without explicit approval.

## 3. Target Phase 2 architecture

```text
Admin browser
    │ HTTPS + authenticated session
    ▼
Internet-facing reverse proxy / application server
    ├─ Admin authentication and authorization
    ├─ Meeting and calendar control API
    ├─ Audit log and job state
    └─ Local worker queue
          ├─ Authorized visible Meet browser + FFmpeg capture
          ├─ faster-whisper CPU transcription
          ├─ Optional local Ollama analysis
          └─ Report/review/export services
    │
    ├─ Private SQLite initially, migration boundary documented
    ├─ Private local data volume
    └─ Google Calendar read-only integration
```

The capture browser must remain on the authorized machine. The internet-facing page controls and observes the job; it must not expose Chrome remote debugging, the profile directory, FFmpeg ports, or raw file paths.

## 4. Phase 2 workstreams

### 2.1 Security and deployment decision

Before code is exposed:

- Choose the approved access model: company VPN/private network, authenticated tunnel, or approved HTTPS host.
- Decide whether processing remains on Ben's PC or moves to an approved internal worker machine.
- Define domain, TLS certificate ownership, backup policy, retention, and incident contact.
- Document the threat model and data classification for recordings, transcripts, reports, service-account keys, and calendar metadata.
- Add a deployment-specific `.env` contract with no secrets committed.

Acceptance criteria:

- A written deployment decision exists.
- The app is unreachable without HTTPS and authentication.
- Secrets are provided through local environment/secret storage only.
- A rollback procedure is documented.

### 2.2 Admin identity and authorization

Implement an admin boundary before any public route:

- Initial single-admin login with a strong password hash or approved company identity provider.
- Secure, HttpOnly, SameSite session cookie with expiry and logout.
- Login rate limiting and failed-login audit events.
- Roles: `admin`, `manager`, `reviewer`, and optional `operator`.
- Server-side authorization on every meeting, transcript, report, calendar, and export action.
- CSRF protection for browser mutations.
- Redaction of tokens and private paths from logs and API responses.

Acceptance criteria:

- Unauthenticated requests receive `401`/redirect and cannot load meeting data.
- A reviewer cannot change calendar credentials or deployment settings.
- Every start, stop, retry, export, review, and login event has actor/time/result metadata.
- Security tests cover session expiry, logout, unauthorized IDs, path traversal, and CSRF.

### 2.3 Internet-facing admin page

Replace the local-only assumption with a small authenticated admin console:

- Dashboard overview: system health, active jobs, recent meetings, failures, and consent/admission state.
- Meetings list with filters for date, status, campaign, and calendar source.
- Meeting detail: event metadata, join URL, capture state, recording state, transcript state, analysis state, and audit history.
- Explicit actions: `Discover`, `Queue capture`, `Stop`, `Retry transcription`, `Run analysis`, `Review`, `Export`.
- No public audio player or transcript endpoint without authorization.
- Pagination and bounded response sizes.
- Health endpoint split into public liveness and authenticated readiness/diagnostics.

Acceptance criteria:

- The admin page works from a separate browser over HTTPS.
- Data cannot be accessed by changing an ID in the URL.
- Long work runs in background jobs and the page receives polling/SSE status updates.
- The page clearly distinguishes `discovered`, `scheduled`, `joining`, `waiting_for_admission`, `recording`, `processing`, `completed`, and `failed`.

### 2.4 Google Calendar read-only integration

Add a least-privilege calendar adapter:

- Prefer OAuth for the authorized work account or a deliberately shared calendar identity.
- Request read-only Calendar scope only for the first release.
- Support a configured calendar ID rather than scanning every calendar.
- Import event ID, title, start/end, organizer, attendees where permitted, conference link, and event updated time.
- Store a local event snapshot and a stable event-to-meeting mapping.
- Deduplicate by calendar ID + event ID + event update time.
- Do not send invitations, modify events, or create bookings in Phase 2A.

Shared-calendar rule:

- If the work account/service identity can read the shared calendar, it can discover the event and its Meet link.
- If the bot account is not invited, it may still navigate using the authorized Google session and request entry where Google permits it.
- Host admission, organization restrictions, and “who can join” settings remain authoritative.
- The UI must show `waiting_for_admission` or `admission_denied`; it must never report a successful join based only on calendar access.

Acceptance criteria:

- Calendar read works with the minimum approved scope.
- A shared-calendar event with a Meet link creates one local meeting candidate.
- Events without a Meet link are ignored safely.
- Revoked/expired access is visible and does not expose tokens.
- No calendar event is modified by tests.

### 2.5 Policy-controlled meeting capture

Add a capture policy object to each meeting:

- `capture_mode`: manual, scheduled, or calendar-discovered.
- `authorization_basis`: attendee, shared-calendar, explicit admin approval.
- `consent_required`: true by default.
- `admission_policy`: wait, stop-after-timeout, or manual-cancel.
- `max_wait_seconds` and `max_duration_seconds`.
- approved browser profile reference, never the profile contents.

Lifecycle:

```text
calendar_discovered
  → admin_approved
  → joining
  → needs_authentication / waiting_for_admission
  → recording
  → meeting_ended
  → transcribing
  → transcribed
  → analysis_queued / reviewed
```

The browser remains visible and uses normal Google authentication. The worker records only after the configured consent condition and successful meeting state are confirmed.

Acceptance criteria:

- A non-invited but calendar-authorized event can be discovered and opened without bypassing Meet controls.
- A waiting-room meeting remains visibly waiting and times out safely.
- A denied or expired meeting is marked accurately.
- The bot never claims recording merely because the URL opened.
- Stop and timeout always terminate FFmpeg and browser resources.

### 2.6 Processing job model

Separate capture, transcription, analysis, and export jobs:

- Add durable job records with type, status, attempt count, timestamps, error, and actor.
- Make every stage idempotent by meeting and artifact version.
- Add retry limits and exponential backoff for local transient failures.
- Keep analysis opt-in until its evidence tests pass.
- Record model name, compute type, processing duration, and input artifact hash.
- Add retention cleanup as an explicit admin action or scheduled policy, never an accidental startup behavior.

Acceptance criteria:

- Restarting the server does not duplicate jobs or lose terminal states.
- A failed transcription can be retried without duplicate transcript segments.
- Analysis cannot start without a valid persisted transcript.
- Export cannot run against an unauthorized meeting.

### 2.7 Evidence-based DME/CGM analysis

After the secured processing path is stable:

- Run the existing eight-stage pipeline explicitly against persisted transcripts.
- Load the versioned DME/CGM Markdown/YAML knowledge sources.
- Require evidence segment IDs for material findings.
- Use `unknown`/`not_assessable` where evidence is absent.
- Score qualification, discovery, objections, commercial discussion, close, opener handoff, and closer performance.
- Validate the final report with Pydantic before persistence.
- Store report version, model, prompt/config version, transcript ID, and evidence references.
- Run the same analysis twice and compare schema validity, duplicate behavior, and material output stability.

Acceptance criteria:

- One approved non-sensitive transcript produces a retrievable report.
- Every material claim is traceable to transcript segments or marked unknown.
- DME and CGM rules are not mixed without a selected campaign.
- No clinical, payer, or commercial fact is invented.

### 2.8 Review, Google Sheets, and audit operations

- Make report review the human approval gate before export.
- Show report evidence beside the transcript.
- Keep Sheets export manual and audit logged.
- Add export idempotency key to avoid duplicate rows on repeated clicks.
- Add a dedicated test worksheet or spreadsheet separate from production data.
- Add audit record containing actor, meeting, report version, destination, result, and timestamp.
- Keep calendar and Sheets credentials separate with separate scopes.

Acceptance criteria:

- A reviewer can correct a report and record the reason.
- Only an approved report can be exported.
- Repeating an export does not silently create duplicates.
- Production and test spreadsheet destinations are visibly distinct.

## 5. Data model additions

Planned entities:

- `admin_users` / external identity mapping
- `sessions` or server-side session references
- `calendar_connections`
- `calendar_sources`
- `calendar_events`
- `meeting_authorizations`
- `jobs`
- `audit_events`
- `report_reviews` extensions for approval/export state

Every entity containing user, calendar, recording, transcript, or report data requires an owner/tenant boundary before multi-user access is enabled.

## 6. API target surface

All routes require authentication unless explicitly marked liveness-only:

```text
GET    /health
GET    /api/v2/admin/me
POST   /api/v2/admin/logout
GET    /api/v2/calendar/status
POST   /api/v2/calendar/connect
GET    /api/v2/calendar/events
POST   /api/v2/calendar/events/{event_id}/discover
GET    /api/v2/meetings
POST   /api/v2/meetings/{id}/approve-capture
POST   /api/v2/meetings/{id}/stop
POST   /api/v2/meetings/{id}/retry-transcription
POST   /api/v2/meetings/{id}/run-analysis
GET    /api/v2/meetings/{id}/transcript
GET    /api/v2/meetings/{id}/report
POST   /api/v2/meetings/{id}/review
POST   /api/v2/meetings/{id}/export/sheets
GET    /api/v2/jobs/{id}
GET    /api/v2/audit-events
```

The existing `/api/v1` local routes should not be exposed publicly until authentication and authorization are added, or they should be bound to loopback/private network only.

## 7. Testing strategy

### Unit tests

- Calendar event parsing and deduplication.
- Meet URL extraction and validation.
- Authorization policy decisions.
- Session/cookie security.
- Job state transitions and idempotency.
- Evidence citation validation.
- Sheets export deduplication.

### Integration tests

- OAuth/calendar token fixture with no real credentials.
- Shared-calendar event fixture creates a meeting candidate.
- No-Meet-link event is ignored.
- Authorized non-attendee flow reaches `waiting_for_admission` without claiming success.
- Isolated SQLite restart/retry tests.
- Full transcript → report → review → Sheets test using synthetic/non-sensitive content.

### Manual supervised tests

- HTTPS login from a second browser.
- Authorized calendar event discovery.
- A real approved Meet where the user controls admission and consent.
- Capture end detection and cleanup.
- Report evidence review.
- Export to a dedicated test Sheet.

## 8. Delivery gates

### Phase 2A — Secure admin shell

Complete authentication, HTTPS decision, authorization, audit events, and protected admin dashboard. No calendar or unattended capture yet.

### Phase 2B — Calendar discovery

Complete read-only calendar connection, shared-calendar event import, deduplication, and clear authorization/admission states.

### Phase 2C — Controlled scheduled capture

Complete policy-based capture, visible browser lifecycle, timeout/stop behavior, and job durability.

### Phase 2D — Verified intelligence

Complete explicit analysis, evidence-linked reports, human review, and controlled Sheets export.

Do not advance a gate based on a plan alone; record test evidence in the worklog.

## 9. Deferred work

- Automatic invitations or calendar event creation.
- CRM writes, outbound email, booking, or follow-up automation.
- Meeting admission bypass or unattended use of unauthorized accounts.
- Public transcript/audio sharing.
- Multi-tenant billing and customer self-service.
- Production deployment before security review and explicit hosting approval.
