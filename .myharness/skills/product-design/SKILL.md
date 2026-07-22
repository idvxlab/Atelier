---
name: product-design
description: Product and industrial-design domain guidance for Atelier: user scenarios, functions, form language, CMF, render deliverables, and critique focus.
license: MIT
metadata:
  audience: design-research, design-planner, design-designer, design-critic
  workflow: ai-design-harness
  domain_type: product_design
---

# Product Design Skill

This skill supports `product_design` runs. It is a first-pass domain framework:
use it to keep the workflow coherent, then deepen the professional details with
future references.

## 1. Domain Positioning

`product_design` covers product and industrial-design concepts expressed as
rendered images, not manufacturing-ready engineering packages.

Typical briefs:

- consumer electronics, appliances, devices, tools, furniture, lighting
- campus or cultural products when the object itself is the design focus
- product CMF, usage scene, hero render, and detail render exploration

The expected final result is a curated PNG set plus `00-gallery.html`.

## 2. Scope Fields

Read `brief.json::resolvedScope.domain_scope`:

```json
{
  "user_context": {
    "target_user": "string",
    "usage_scenario": "string",
    "environment": "string"
  },
  "function_experience": {
    "core_functions": ["string"],
    "interaction_mode": "string",
    "experience_goal": "string"
  },
  "form_material": {
    "form_direction": "string",
    "material_cmf": "string",
    "scale_or_portability": "string"
  }
}
```

If fields are missing, infer careful defaults from the brief and record them in
planning assumptions. Primary should ask the user only when the missing field
would materially change the design direction.

## 3. Research Guidance

Research should collect references for:

- similar product categories and competing objects
- usage contexts and body/object scale cues
- material, color, and finish references
- interface, detail, mechanism, and portability examples
- lifestyle images that show the product's likely environment

Reference images should be saved in `research/assets/` and described by role:
`competitor`, `usage_context`, `cmf`, `detail`, or `lifestyle` when possible.
The current asset tool may still use generic kinds such as `peer` or `other`;
record the more specific role in descriptions until the tool schema is expanded.

## 4. Planner Guidance

Planner should translate the brief into an executable concept plan:

- product thesis: what problem the product appears to solve
- target user and scenario
- functional priorities
- form language and proportions
- CMF direction
- image-generation plan tied to deliverable categories

Recommended deliverable categories:

- hero product render
- usage scenario render
- detail or interaction render
- CMF/material board
- optional form exploration sheet

## 5. Designer Guidance

Designer should produce PNGs that look like product concept renderings.

Each image prompt should include:

- product object name
- target user and usage scene
- core function visible in the image
- form language and silhouette
- material/finish/color direction
- view type: hero, usage, detail, CMF, or exploration

Avoid images that only look like abstract branding graphics.

## 6. Critic Guidance

Critic should evaluate:

- whether function is visually understandable
- whether form and CMF match the user/context
- whether scale and interaction feel plausible
- whether deliverables cover hero, usage, detail, and material views
- whether the PNGs read as product design, not just poster graphics

## 7. Later Professional Deepening

Future work should add stronger references for:

- CMF methods
- ergonomics and human factors
- product semantics
- manufacturability heuristics
- category-specific render conventions
