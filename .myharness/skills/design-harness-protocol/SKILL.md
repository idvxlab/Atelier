---
name: design-harness-protocol
description: "Simplified Atelier design workflow protocol: run layout, bus messages, handoff contracts, and package rules."
license: MIT
metadata:
  audience: design-primary, design-research, design-planner, design-designer, design-critic
  workflow: ai-design-harness
---
# Design Harness Protocol

This skill defines the simplified Atelier design workflow.

## Runtime Mapping

- `ask_user`: structured clarification.
- `spawn_agent` / `spawn_agents`: subagent execution.
- `run_init`: create run directory and `brief.json`.
- `design_bus_post` / `design_bus_read`: phase handoff.
- `research_fetch`, `research_asset_discover`, `research_asset_fetch`, `research_asset_validate`: research and reference assets.
- `image_generate`, `image_edit`: image creation and editing.
- `artifact_lint`: validation.
- `export_package`: final package.

Do not use OpenCode-only tool names such as `question` or `task`.

## Workflow

Use this single-path chain:

`design-primary -> design-research -> design-planner -> design-designer -> design-critic -> export_package`

There are no design batches in the migrated workflow.

## Run Directory

`run_init` returns `runId` and `runDir`.

Before calling `run_init`, Primary should derive a readable run slug and pass it as `runIdOverride` whenever possible. The slug should be lowercase ASCII, stable, and descriptive, such as `tongji-idvx-lab-visual-system`. Also store a human-facing `run_name` or `human_title` in `resolvedScope`. This keeps both the internal run directory and `outputs/runs/<runId>/final/` easy to find later.

Expected layout:

```text
<runDir>/
  brief.json
  bus.jsonl
  research/
    evidence.json
    research.md
    brand_lock.md
    assets/
      manifest.json
      validation.json
  plan/
    design_direction.md
    deliverable_manifest.json
    acceptance_criteria.md
    task_breakdown.md
  artifacts/
    generated-images/
    edits/
    00-gallery.html
    artifact-manifest.json
  review/
    critique.md
    critique.json
```

`export_package` writes the final deliverable to `outputs/runs/<runId>/final/`.

## Bus Messages

Canonical message types:

- `kickoff`
- `research_done`
- `research_followup`
- `plan_done`
- `design_done`
- `evaluator_pass`
- `evaluator_fail`
- `status`

Sender names:

- `design-primary`
- `design-research`
- `design-planner`
- `design-designer`
- `design-critic`

Use `evaluator_pass` and `evaluator_fail` for critic verdicts to stay compatible with the tool schema.

## Done Conditions

Research is done when evidence, notes, brand lock, and asset validation are written or limitations are clearly documented.

Research should usually save a broad reference image library in `research/assets/`, not only the exact assets expected to appear in the final design. Aim for enough official, environmental, application, and peer images that Designer can choose a smaller subset later. Unused but valid references remain useful for audit, critique, and later redesign.

Planning is done when direction, manifest, acceptance criteria, and task breakdown are written.

Design is done when PNG artifacts, gallery, artifact manifest, and lint result exist.

Critique is done when critique files exist and a pass/fail bus message is posted.

Package is done when `export_package` returns `ok: true`.

## Failure Handling

If research has no usable public source, document that and continue with a speculative concept.

If image editing fails, try a generated valid reference once, then continue with image generation.

If the critic fails the artifact set, the primary may request exactly one designer repair pass before packaging or reporting remaining risks.
