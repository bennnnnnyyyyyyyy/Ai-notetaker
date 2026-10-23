# Agent Instructions — AI Notetaker

This repository is a local-first Google Meet capture and meeting-intelligence prototype. The current implementation is a FastAPI backend in `backend/` and a static frontend in `frontend/`. Local runtime data belongs in `data/` and must never be committed.

## Before changing code

1. Read [`documentation/README.md`](documentation/README.md).
2. Read [`documentation/architecture/ARCHITECTURE.md`](documentation/architecture/ARCHITECTURE.md) for current boundaries.
3. Read the relevant plan in [`documentation/plans/`](documentation/plans/) before implementing a non-trivial feature.
4. Check [`documentation/operations/WORKLOG.md`](documentation/operations/WORKLOG.md) for the latest verified state.

## Documentation authorities

- `documentation/architecture/` describes what exists now.
- `documentation/plans/` describes approved target work.
- `documentation/planning/` is temporary working material.
- `documentation/operations/` records completed work and runtime changes.
- `documentation/reviews/` records audits and verification results.
- `documentation/reference/` stores background material.
- Do not put project documentation in `frontend/`; that folder is application UI.

## Safety and implementation rules

- State assumptions before coding and make focused changes.
- Never bypass Google authentication, admission controls, recording consent, or browser permission prompts.
- Never commit recordings, transcripts containing meeting content, browser profiles, credentials, `.env` files, or local databases.
- Do not make paid API, cloud-hosting, or production-data changes without explicit approval.
- Do not delete broad directories or reset unrelated user changes.
- Use PowerShell only. This PC has no `cmd`, no admin privileges, and no dependable PATH; use `py -3` and explicit paths when needed.
- Do not claim a real meeting capture, audio-device test, or browser test unless it actually happened.

## Verification handoff

Run safe checks proportional to the change. At minimum for backend changes:

```powershell
py -3 -m compileall -q backend
py -3 -c "from backend.main import app; print('import: OK')"
```

Record meaningful implementation changes in `documentation/operations/WORKLOG.md` with Objective, Actions Completed, System Result, and Safety Status.
