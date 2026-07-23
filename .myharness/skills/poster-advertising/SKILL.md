---
name: poster-advertising
description: "Poster, advertising, event key-visual, and campaign communication guidance for Atelier: message hierarchy, visual hook, media adaptation, and critique focus."
license: MIT
metadata:
  audience: design-research, design-planner, design-designer, design-critic
  workflow: ai-design-harness
  domain_type: poster_advertising_design
---

# Poster & Advertising Design Skill

This skill supports `poster_advertising_design` runs. It is a first-pass domain
framework for communication-first visuals.

## 1. Domain Positioning

`poster_advertising_design` covers:

- standalone posters
- event key visuals
- advertising campaign images
- recruitment or announcement posters
- social-format adaptations of one communication idea

Use this domain when the main deliverable is the communication visual itself.
If the brief asks for a broader identity and merchandise system, prefer
`brand_cultural_design`.

## 2. Scope Fields

Read `brief.json::resolvedScope.domain_scope`:

```json
{
  "communication_goal": {
    "campaign_goal": "string",
    "target_action": "string",
    "audience": "string"
  },
  "message_hierarchy": {
    "key_message": "string",
    "supporting_info": ["string"],
    "info_density": "minimal | moderate | dense | string"
  },
  "visual_direction": {
    "visual_tone": "string",
    "visual_hook": "string",
    "format_requirements": "string"
  }
}
```

Primary should ask for missing key message, audience/action, or format only
when these are not inferable from the brief.

## 3. Research Guidance

Research should collect references for:

- similar campaign or event visuals
- poster systems and typographic hierarchy examples
- visual tone and mood references
- media-format examples such as portrait poster, banner, and social square
- cultural or subject-matter references that affect imagery

Research should prioritize communication references, not only institutional
identity assets.

## 4. Planner Guidance

Planner should define:

- communication thesis
- key message and supporting information hierarchy
- visual hook
- format set and aspect ratios
- image-generation plan tied to message hierarchy

Recommended deliverable categories:

- main poster
- key visual
- color system board
- typography and information hierarchy board
- social adaptation

Optional additional categories:

- poster series variation
- banner adaptation
- typographic/detail crop
- media placement mockup

These are categories. If the brief names multiple media formats, campaign
phases, or poster sizes, Planner may expand one category into several concrete
PNG entries in `deliverable_manifest.json`.

## 5. Designer Guidance

Designer should produce PNGs that communicate quickly and clearly.

Each image prompt should include:

- key message or headline intent
- visual hook
- hierarchy: what should be seen first, second, third
- tone and audience
- format and aspect ratio
- required language or text handling

Avoid generic decorative graphics with no message hierarchy.

## 6. Critic Guidance

Critic should evaluate:

- whether the message is clear within a few seconds
- whether hierarchy supports the intended action
- whether visual impact fits the audience and topic
- whether adaptations retain the same campaign idea
- whether the outputs are usable as poster/advertising visuals

## 7. Later Professional Deepening

Future work should add stronger references for:

- campaign strategy
- poster typography
- information hierarchy systems
- media adaptation rules
- copy/image relationship
