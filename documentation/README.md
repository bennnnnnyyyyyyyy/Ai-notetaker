# AI Notetaker Documentation

This is the canonical documentation index. Keep the code folders focused on code and the documentation folders focused on decisions, plans, evidence, and handoff.

| Folder | Authority | Use it for |
|---|---|---|
| [`architecture/`](architecture/) | Current state | What the system actually does now |
| [`plans/`](plans/) | Target state | Approved milestones and feature designs |
| [`planning/`](planning/) | Working state | Temporary investigations and task notes |
| [`operations/`](operations/) | Historical evidence | Completed work, migrations, and runtime checks |
| [`reviews/`](reviews/) | Guardrails | Audits, test sweeps, and known risks |
| [`reference/`](reference/) | Background | Imported or historical material |

## Collaboration rules

- Read `AGENTS.md` at the repository root before making changes.
- Update the worklog when implementation meaningfully changes behavior, schema, or setup.
- Link plans to architecture and worklog entries with relative links.
- Keep secrets, recordings, transcripts, browser profiles, and databases out of documentation and Git.
- A plan is not evidence of completion; the worklog and verification output are evidence.

## Quick links

- [Architecture](architecture/ARCHITECTURE.md)
- [Master plan](plans/MASTER_PLAN.md)
- [Plan checklist](plans/checklist.md)
- [Worklog](operations/WORKLOG.md)
- [Initial review](reviews/INITIAL_REVIEW.md)
- [Phase 1 completion record](operations/PHASE_1_COMPLETE.md)
- [Phase 2 plan](plans/PHASE_2_PLAN.md)
