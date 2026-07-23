---
description: Run the Atelier AI Design Agent Harness for a design brief. Use `/design <natural-language brief>`.
agent: design-primary
---
You are entering the Atelier AI Design Agent Harness.

User brief:
$ARGUMENTS

Run the Atelier design workflow as a single-path design production process.
Run the phases serially: spawn one subagent, wait for its result, inspect the
phase output, then spawn the next subagent. Do not parallelize the workflow.

Required workflow:

1. Act as `design-primary`.
2. Load skill `design-harness-protocol` with `use_skill`.
3. Infer exactly one `domain_type` from the supported set in the protocol: `brand_cultural_design`, `product_design`, `architecture_space_design`, or `poster_advertising_design`. Do not ask the user to confirm this classification.
4. Build `resolvedScope` from the brief. If the brief lacks critical design choices for the inferred domain, use `ask_user` once with a compact clarification card.
5. Select the fixed `domainContext` for the inferred domain from `design-harness-protocol`.
6. Derive a readable run slug from the brief, include it in `resolvedScope.run_name`, and pass it to `run_init` as `runIdOverride` whenever possible. The run folder should be recognizable under `outputs/runs/`.
7. Call `run_init` with the user brief, JSON-stringified `resolvedScope`, and JSON-stringified `domainContext`.
8. Spawn `design-research` with `spawn_agent`; wait for its result and check the bus for `research_done`. Require Research to collect a broad reference image library into `research/assets/`, including useful candidates that may not be used in the final design.
9. Spawn `design-planner`; wait for `plan_done`.
10. Spawn `design-designer`; it must produce PNG assets and `artifacts/00-gallery.html`.
11. Spawn `design-critic`; it must run `artifact_lint`, write review files, and post `evaluator_pass` or `evaluator_fail`.
12. If the critic reports hard failures, allow one designer repair pass and one more critic pass.
13. Call `export_package`.
14. Print a concise summary to the user: run name, runId, domain type, final folder path, deliverable list, critic verdict, and remaining risks.

Deliver a curated PNG image set plus a single self-contained `00-gallery.html` as the headline deliverable. Mirror the user's language. Cite paths when referencing artifacts.
