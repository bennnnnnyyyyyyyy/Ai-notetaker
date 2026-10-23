---
name: post-patch-validation
description: Validate AI Notetaker changes with safe local checks and produce an honest handoff. Use after editing code, configuration, documentation workflows, or project-local skills.
---

# Post-patch validation

- Inspect the changed files and verify links to new documentation resolve.
- For Python changes run `py -3 -m compileall -q backend`.
- For application changes import the FastAPI app and run only safe local endpoint smoke tests.
- For skill changes verify YAML frontmatter and that each skill has only a required `SKILL.md` unless a resource is needed.
- Do not claim browser, audio, FFmpeg, Ollama, or real-meeting verification unless it was actually run.
- Report checks passed, checks blocked by missing tools/models/devices, and the next manual test separately.
