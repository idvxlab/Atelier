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
- `spawn_agent`: subagent execution.
- `run_init`: create run directory and `brief.json`.
- `design_bus_post` / `design_bus_read`: phase handoff.
- `research_fetch`, `research_asset_discover`, `research_asset_fetch`, `research_asset_validate`: research and reference assets.
- `image_generate`, `image_edit`: image creation and editing.
- `artifact_lint`: validation.
- `export_package`: final package.

Use the Atelier runtime tools named above when coordinating the workflow.
For this design workflow, subagent execution is serial: Research finishes before
Planner starts, Planner finishes before Designer starts, and Designer finishes
before Critic starts.

## Workflow

Use this single-path chain:

`design-primary -> design-research -> design-planner -> design-designer -> design-critic -> export_package`

Each `/design` request produces one run with one final curated artifact set.

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
  "required_outputs": ["string"],
  "optional_outputs": ["string"],
  "conditional_outputs": ["string"],
  "consistency_anchor": ["string"],
  "evaluation_focus": ["string"],
  "research_keywords": ["string"],
  "common_outputs": ["string"]
}
```

`deliverable_categories` and `required_outputs` are planning categories. Planner
may expand a category into multiple concrete PNG entries when the brief asks for
several applications, views, or formats. Example: `application and merchandise`
may become separate manifest items for tote bag, T-shirt, badge, packaging, and
signage while keeping the same `deliverable_category` value for traceability.
Do not reduce named multiple outputs to a single generic image when the request
clearly asks for several separate deliverables.

`conditional_outputs` are optional at the domain level but become required once
Planner selects them for the current brief. Use them as adaptive triggers:
complex product structure can add an exploded view; many functions can add a
function annotation board; public communication needs can add a poster or
marketing visual; interaction-heavy concepts can add an interaction flow; and
spatial sequence complexity can add a circulation or sequence diagram.

`consistency_anchor` names the stable visual subject for the whole run. The
anchor changes by domain: product form and CMF for product design,
logo/motif/identity for brand-cultural design, spatial language and material
atmosphere for architecture-space design, and key visual plus copy hierarchy
for poster-advertising design. Planner records the anchor in
`design_system.json`; Designer should establish a canonical anchor image or
reference set early, then use `image_edit` from that anchor whenever a later
deliverable needs visual continuity.

Initial domain-context table:

```json
{
  "brand_cultural_design": {
    "label": "Brand & Cultural Design",
    "description": "Brand, institutional identity, cultural merchandise, and applied visual systems.",
    "professional_factors": ["identity recognition", "cultural translation", "visual-system coherence", "audience fit", "application consistency"],
    "reference_strategy": ["official identity assets", "cultural context", "peer brand systems", "merchandise and application examples"],
    "deliverable_categories": ["key visual", "color system board", "typography system board", "application and merchandise", "visual-system board"],
    "required_outputs": ["key visual PNG", "color system board PNG", "typography system board PNG", "application/merchandise PNG set", "visual-system board PNG", "gallery HTML"],
    "optional_outputs": ["poster series PNG", "social media card PNG", "environmental application PNG", "motif/detail board PNG"],
    "conditional_outputs": ["add separate merchandise mockups when named by the user", "add poster or campaign visuals when the brief has a communication goal", "add signage/environmental applications when the identity appears in space"],
    "consistency_anchor": ["official or derived logo/mark", "core motif", "palette tokens", "typography roles", "layout rhythm"],
    "evaluation_focus": ["recognizability", "cultural fit", "system consistency", "reference grounding", "production readiness"],
    "research_keywords": ["official site", "logo", "visual identity", "brand guideline", "cultural symbol", "merchandise"],
    "common_outputs": ["key visual PNG", "color system board PNG", "typography system board PNG", "application/merchandise PNG set", "visual-system board PNG", "gallery HTML"]
  },
  "product_design": {
    "label": "Product Design",
    "description": "Product and industrial-design concepts expressed as renderings and usage visuals.",
    "professional_factors": ["user scenario", "core function", "form language", "CMF", "ergonomics", "manufacturing plausibility"],
    "reference_strategy": ["competing products", "usage scenarios", "materials and finishes", "details and mechanisms", "lifestyle context"],
    "deliverable_categories": ["hero render", "three-view", "usage scene", "detail render", "CMF board"],
    "required_outputs": ["hero product render PNG", "three-view PNG", "usage scene PNG", "detail render PNG", "CMF board PNG", "gallery HTML"],
    "optional_outputs": ["exploded view PNG", "scale reference PNG", "interaction flow PNG", "form variation PNG", "packaging/display PNG"],
    "conditional_outputs": ["add exploded view for complex structure or visible internal modules", "add function annotation board for multi-function products", "add interaction flow for screen, voice, gesture, or service interactions", "add poster/marketing visual when the brief asks for launch or promotion", "add scale reference when size matters to usage"],
    "consistency_anchor": ["canonical product form", "three-view proportions", "CMF palette", "control/button placement", "surface texture and detail language"],
    "evaluation_focus": ["function clarity", "user fit", "form-material coherence", "scale plausibility", "render completeness"],
    "research_keywords": ["product reference", "industrial design", "CMF", "ergonomics", "usage scenario", "detail design"],
    "common_outputs": ["hero product render PNG", "three-view PNG", "usage scene PNG", "detail render PNG", "CMF board PNG", "gallery HTML"]
  },
  "architecture_space_design": {
    "label": "Architecture & Space Design",
    "description": "Architecture, interior, exhibition, and spatial concepts expressed as atmospheric renderings.",
    "professional_factors": ["site relationship", "program", "spatial sequence", "scale", "material atmosphere", "light"],
    "reference_strategy": ["site/context images", "precedent spaces", "materials", "lighting atmosphere", "circulation and zoning examples"],
    "deliverable_categories": ["exterior or arrival view", "interior key view", "plan or zoning diagram", "circulation or spatial sequence", "material atmosphere board"],
    "required_outputs": ["exterior/arrival view PNG", "interior key view PNG", "plan/zoning diagram PNG", "circulation/spatial sequence PNG", "material atmosphere board PNG", "gallery HTML"],
    "optional_outputs": ["site relation view PNG", "section perspective PNG", "facade/detail vignette PNG", "day-night atmosphere PNG", "human-scale scene PNG"],
    "conditional_outputs": ["add site relation view when urban/context fit matters", "add section perspective when vertical organization matters", "add facade/detail vignette when envelope or craft is important", "add day-night atmosphere when lighting experience is central"],
    "consistency_anchor": ["massing or spatial concept", "material palette", "light atmosphere", "human scale cues", "circulation logic"],
    "evaluation_focus": ["spatial logic", "site fit", "atmosphere", "material coherence", "human scale"],
    "research_keywords": ["architecture precedent", "interior design", "exhibition design", "spatial atmosphere", "material palette", "site context"],
    "common_outputs": ["exterior/arrival PNG", "interior key view PNG", "plan/zoning PNG", "circulation/sequence PNG", "material board PNG", "gallery HTML"]
  },
  "poster_advertising_design": {
    "label": "Poster & Advertising Design",
    "description": "Posters, event key visuals, and campaign communication images.",
    "professional_factors": ["communication goal", "message hierarchy", "visual hook", "medium adaptation", "copy-image relationship"],
    "reference_strategy": ["campaign references", "poster systems", "typographic hierarchy", "media formats", "audience mood"],
    "deliverable_categories": ["main poster", "key visual", "color system board", "typography and hierarchy board", "social adaptation"],
    "required_outputs": ["main poster PNG", "key visual PNG", "color system board PNG", "typography/hierarchy board PNG", "social adaptation PNG", "gallery HTML"],
    "optional_outputs": ["poster series variation PNG", "banner adaptation PNG", "copy hierarchy detail PNG", "media placement mockup PNG"],
    "conditional_outputs": ["add poster series variations for multi-message campaigns", "add banner or social adaptations when multiple media are requested", "add copy hierarchy detail when text density is high", "add placement mockup when media context matters"],
    "consistency_anchor": ["main key visual", "headline hierarchy", "palette tokens", "typography roles", "graphic device"],
    "evaluation_focus": ["message clarity", "visual impact", "hierarchy", "audience fit", "format readiness"],
    "research_keywords": ["poster design", "advertising campaign", "key visual", "event poster", "typographic hierarchy", "social media visual"],
    "common_outputs": ["main poster PNG", "key visual PNG", "color system board PNG", "typography/hierarchy board PNG", "social adaptation PNG", "gallery HTML"]
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

Research is done when evidence, notes, brand lock, asset validation, and the
canonical `research_done` bus message are present. If the Research subagent
returns `Error:`, Primary must not treat partial files as completion and must
not start Planner until the same phase is retried/resumed or the run is
reported blocked.

Research should usually save a broad reference image library in `research/assets/`, not only the exact assets expected to appear in the final design. Aim for enough official, environmental, application, and peer images that Designer can choose a smaller subset later. Unused but valid references remain useful for audit, critique, and later redesign.

Planning is done when design system, design plan, manifest, acceptance
criteria, task breakdown, and the canonical `plan_done` bus message are present.

Design is done when PNG artifacts, gallery, artifact manifest, lint result, and
the canonical `design_done` bus message exist.

Critique is done when critique files exist and a pass/fail bus message is posted.

Package is done when `export_package` returns `ok: true`.

## Failure Handling

If research has no usable public source, document that and continue with a speculative concept.

If image editing fails, try a generated valid reference once, then continue with image generation.

If the critic fails the artifact set, the primary may request exactly one designer repair pass before packaging or reporting remaining risks.

If a subagent returns `Error: sub-agent ... did not complete`, that phase is not
done. Do not advance to the next phase based only on partial files. Retry or
resume the same phase once when the cause is transient; otherwise report the
blocked phase and the missing canonical bus message.
