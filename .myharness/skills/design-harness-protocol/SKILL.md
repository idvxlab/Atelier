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

## Design Domains

Atelier uses a small fixed domain set for the current workflow. `design-primary`
infers `domain_type` automatically from the brief; do not ask the user to choose
or confirm it unless the user explicitly corrects the classification later.

Supported `domain_type` values:

- `brand_cultural_design`: brand identity, cultural merchandise, institutional visual systems, campaign extensions, and branded applications.
- `product_design`: product or industrial-design concepts, including product appearance, usage scenes, CMF, and detail renders.
- `architecture_space_design`: architecture, interior, spatial, exhibition, retail, and environmental concept design.
- `poster_advertising_design`: poster, advertising, event key visual, and campaign communication design.

The final deliverable shape is always a curated PNG image set plus one polished
`artifacts/00-gallery.html`. The harness produces concept/effect images and
presentation material, not CAD, BIM, engineering drawings, manufacturing files,
or construction documents.

## Scope Contract

`resolvedScope` stores the clarified user request. It should answer: what is
being designed, for whom, in what language, with what intent, style preference,
and constraints. It must include `domain_type`, but it should not become a
general professional rulebook.

Recommended shape:

```json
{
  "run_name": "short-ascii-slug",
  "human_title": "Human-readable title",
  "domain_type": "brand_cultural_design | product_design | architecture_space_design | poster_advertising_design",
  "target": "string",
  "audience": "string",
  "language": "zh | en | mixed",
  "deliverable_intent": "string",
  "style_preferences": "string",
  "constraints": "string",
  "domain_scope": {}
}
```

`domain_scope` is domain-specific:

- `brand_cultural_design`: `mind_identity`, `behavior_identity`, `visual_identity`.
- `product_design`: `user_context`, `function_experience`, `form_material`.
- `architecture_space_design`: `site_context`, `program_spatial`, `atmosphere_material`.
- `poster_advertising_design`: `communication_goal`, `message_hierarchy`, `visual_direction`.

`domainContext` stores the fixed professional context for the chosen domain. It
is selected from the harness domain table, saved beside `resolvedScope`, and
passed through bus payloads and subagent task prompts.

Recommended shape:

```json
{
  "domain_type": "product_design",
  "label": "Product Design",
  "description": "string",
  "professional_factors": ["string"],
  "reference_strategy": ["string"],
  "deliverable_categories": ["string"],
  "evaluation_focus": ["string"],
  "research_keywords": ["string"],
  "common_outputs": ["string"]
}
```

Initial domain-context table:

```json
{
  "brand_cultural_design": {
    "label": "Brand & Cultural Design",
    "description": "Brand, institutional identity, cultural merchandise, and applied visual systems.",
    "professional_factors": ["identity recognition", "cultural translation", "visual-system coherence", "audience fit", "application consistency"],
    "reference_strategy": ["official identity assets", "cultural context", "peer brand systems", "merchandise and application examples"],
    "deliverable_categories": ["key visual", "poster", "merchandise mockup", "social/application visual", "visual-system board"],
    "evaluation_focus": ["recognizability", "cultural fit", "system consistency", "reference grounding", "production readiness"],
    "research_keywords": ["official site", "logo", "visual identity", "brand guideline", "cultural symbol", "merchandise"],
    "common_outputs": ["poster PNG", "merchandise PNG", "social card PNG", "application mockup PNG", "gallery HTML"]
  },
  "product_design": {
    "label": "Product Design",
    "description": "Product and industrial-design concepts expressed as renderings and usage visuals.",
    "professional_factors": ["user scenario", "core function", "form language", "CMF", "ergonomics", "manufacturing plausibility"],
    "reference_strategy": ["competing products", "usage scenarios", "materials and finishes", "details and mechanisms", "lifestyle context"],
    "deliverable_categories": ["hero render", "usage scene", "detail render", "CMF board", "form exploration"],
    "evaluation_focus": ["function clarity", "user fit", "form-material coherence", "scale plausibility", "render completeness"],
    "research_keywords": ["product reference", "industrial design", "CMF", "ergonomics", "usage scenario", "detail design"],
    "common_outputs": ["hero product PNG", "usage scene PNG", "detail PNG", "CMF board PNG", "gallery HTML"]
  },
  "architecture_space_design": {
    "label": "Architecture & Space Design",
    "description": "Architecture, interior, exhibition, and spatial concepts expressed as atmospheric renderings.",
    "professional_factors": ["site relationship", "program", "spatial sequence", "scale", "material atmosphere", "light"],
    "reference_strategy": ["site/context images", "precedent spaces", "materials", "lighting atmosphere", "circulation and zoning examples"],
    "deliverable_categories": ["exterior perspective", "interior perspective", "spatial zoning", "material atmosphere board", "site relation view"],
    "evaluation_focus": ["spatial logic", "site fit", "atmosphere", "material coherence", "human scale"],
    "research_keywords": ["architecture precedent", "interior design", "exhibition design", "spatial atmosphere", "material palette", "site context"],
    "common_outputs": ["exterior/interior PNG", "zoning PNG", "material board PNG", "gallery HTML"]
  },
  "poster_advertising_design": {
    "label": "Poster & Advertising Design",
    "description": "Posters, event key visuals, and campaign communication images.",
    "professional_factors": ["communication goal", "message hierarchy", "visual hook", "medium adaptation", "copy-image relationship"],
    "reference_strategy": ["campaign references", "poster systems", "typographic hierarchy", "media formats", "audience mood"],
    "deliverable_categories": ["main poster", "key visual", "series poster", "social adaptation", "typographic detail"],
    "evaluation_focus": ["message clarity", "visual impact", "hierarchy", "audience fit", "format readiness"],
    "research_keywords": ["poster design", "advertising campaign", "key visual", "event poster", "typographic hierarchy", "social media visual"],
    "common_outputs": ["main poster PNG", "series/adaptation PNG", "key visual PNG", "gallery HTML"]
  }
}
```

## Clarification Contract

Primary may still use `ask_user` to confirm missing user needs. The domain type
itself is not a question. Ask at most one compact clarification card before
`run_init`, and only ask questions that materially change the design direction.

Clarification flow:

1. Infer `domain_type`.
2. Build an initial `resolvedScope`.
3. Select the fixed `domainContext`.
4. Check missing common fields and the selected domain's `domain_scope`.
5. If critical choices are missing, call `ask_user` once.
6. Merge the answer into `resolvedScope`; fill remaining minor gaps with clear defaults.
7. Call `run_init` with `brief`, JSON-stringified `resolvedScope`, and JSON-stringified `domainContext`.

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
    design_system.json
    design_plan.json
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

Planning is done when design system, design plan, manifest, acceptance criteria, and task breakdown are written.

Design is done when PNG artifacts, gallery, artifact manifest, and lint result exist.

Critique is done when critique files exist and a pass/fail bus message is posted.

Package is done when `export_package` returns `ok: true`.

## Failure Handling

If research has no usable public source, document that and continue with a speculative concept.

If image editing fails, try a generated valid reference once, then continue with image generation.

If the critic fails the artifact set, the primary may request exactly one designer repair pass before packaging or reporting remaining risks.
