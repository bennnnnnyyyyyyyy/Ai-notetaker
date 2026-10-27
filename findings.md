# Findings — Reddit Dump

## Current repository baseline

- The app already has a local capture, transcription, local analysis, review, and controlled export direction.
- Google authentication, admission, recording consent, and browser permissions must remain authoritative.
- Current gaps include speaker diarisation, robust Meet lifecycle handling, and real-world verification of some integrations.

## Product signals extracted from the dump

1. Users value in-person and botless capture because visible meeting bots can create client discomfort.
2. Uploading existing recordings is useful and reduces dependence on a live capture path.
3. Users compare note takers on transcript accuracy, summary usefulness, speaker identification, multilingual support, privacy, reliability, integrations, and post-meeting workflow.
4. Useful outputs extend beyond a summary: chapters, decisions, blockers, action items, follow-ups, and visual structures such as timelines or mind maps.
5. Streaming progress/live transcript can make long processing runs feel less opaque.
6. Reliability safeguards are important: idempotency, retrying delayed transcript availability, schema validation, structured logs, and explicit approval before external actions.

## Constraints and interpretation

- The dump includes a separate cloud meeting-bot tutorial. It is reference material only and does not fit the current local-first scope.
- Marketing and Reddit claims are not evidence of performance; benchmark accuracy, latency, and quality locally.
- Privacy and consent are first-class requirements, not optional UX features.

## Scope correction

- The app is completely internal. External-product concerns such as public onboarding, pricing, customer accounts, broad platform coverage, and public SaaS deployment are out of scope.
- Retain only capabilities that improve internal capture, sales review, evidence-backed coaching, controlled internal exports, and auditability.
