---
name: project-workflow
description: Maintain the AI Notetaker repository using its separated architecture, plans, planning notes, operations worklog, and reviews. Use when planning or implementing any non-trivial project change.
---

# Project workflow

1. Read `AGENTS.md`, `documentation/README.md`, the current architecture, and the relevant plan.
2. State assumptions before changing code.
3. Keep stable design in `documentation/architecture/`, approved work in `documentation/plans/`, temporary investigation in `documentation/planning/`, completed evidence in `documentation/operations/`, and audits in `documentation/reviews/`.
4. Update `documentation/plans/checklist.md` when milestone status changes.
5. Add a dated worklog entry for meaningful implementation, schema, setup, or runtime changes.
6. Never treat a plan as proof that work is complete; cite tests or observed runtime output.
