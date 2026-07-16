---
description: Run the AI Design Agent Harness for a graphic/brand design brief. Use `/design <natural-language brief>`.
agent: design-primary
---
You are entering the Atelier AI Design Agent Harness.

User brief:
$ARGUMENTS

Run the simplified Atelier design workflow. This command was migrated from the old OpenCode `/design` command; keep the design intent, but use Atelier's single-path workflow.

Required workflow:

1. Act as `design-primary`.
2. Load skill `design-harness-protocol` with `use_skill`.
3. If the brief lacks critical design choices, use `ask_user` once with a compact clarification card. Do not use OpenCode `question`.
4. Derive a readable run slug from the brief, include it in `resolvedScope.run_name`, and pass it to `run_init` as `runIdOverride` whenever possible. The run folder should be recognizable under `outputs/runs/`.
5. Call `run_init` with the user brief and JSON-stringified `resolvedScope`.
6. Spawn `design-research` with `spawn_agent`; wait for its result and check the bus for `research_done`. Require Research to collect a broad reference image library into `research/assets/`, including useful candidates that may not be used in the final design.
7. Spawn `design-planner`; wait for `plan_done`.
8. Spawn `design-designer`; it must produce PNG assets and `artifacts/00-gallery.html`.
9. Spawn `design-critic`; it must run `artifact_lint`, write review files, and post `evaluator_pass` or `evaluator_fail`.
10. If the critic reports hard failures, allow one designer repair pass and one more critic pass.
11. Call `export_package`.
12. Print a concise summary to the user: run name, runId, final folder path, deliverable list, critic verdict, and remaining risks.

Deliver a curated PNG image set plus a single self-contained `00-gallery.html` as the headline deliverable. Mirror the user's language. Cite paths when referencing artifacts.
