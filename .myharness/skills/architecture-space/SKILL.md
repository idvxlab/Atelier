---
name: architecture-space
description: Architecture, interior, exhibition, and spatial-design domain guidance for Atelier: site, program, spatial sequence, atmosphere, material, and presentation render deliverables.
license: MIT
metadata:
  audience: design-research, design-planner, design-designer, design-critic
  workflow: ai-design-harness
  domain_type: architecture_space_design
---

# Architecture & Space Design Skill

This skill supports `architecture_space_design` runs. It is a first-pass domain
framework for concept/effect images, not CAD, BIM, construction drawings, or
technical detailing.

## 1. Domain Positioning

`architecture_space_design` covers:

- architectural concept design
- interiors and retail spaces
- exhibition, booth, installation, and environmental design
- visitor centers, labs, studios, campus spaces, and cultural spaces

The expected final result is a curated PNG set plus `00-gallery.html`.

## 2. Scope Fields

Read `brief.json::resolvedScope.domain_scope`:

```json
{
  "site_context": {
    "location_or_site_type": "string",
    "context_relationship": "string",
    "environmental_cues": "string"
  },
  "program_spatial": {
    "core_functions": ["string"],
    "spatial_sequence": "string",
    "scale": "string"
  },
  "atmosphere_material": {
    "atmosphere": "string",
    "material_direction": "string",
    "light_strategy": "string"
  }
}
```

Primary should ask the user only when missing function, scale, site, or
atmosphere would lead to a materially different concept.

## 3. Research Guidance

Research should collect references for:

- site/context or analogous environmental images
- precedent buildings, interiors, exhibitions, or spatial installations
- material palette and lighting atmosphere
- circulation, zoning, or public/private relationship examples
- human-scale cues and use scenarios

When real site data is unavailable, collect analogous references and label the
run as a concept based on assumptions.

## 4. Planner Guidance

Planner should define:

- spatial thesis and intended experience
- program/zoning priorities
- site or context relationship
- atmosphere, material, and light direction
- image-generation plan tied to view categories

Recommended deliverable categories:

- exterior perspective or arrival view
- interior perspective or key spatial moment
- spatial zoning / circulation concept image
- material atmosphere board
- optional site relation view or detail vignette

## 5. Designer Guidance

Designer should produce PNGs that read as architectural or spatial concept
presentation images.

Each image prompt should include:

- space type and function
- view type: exterior, interior, zoning, material board, or site relation
- spatial organization and human-scale cues
- atmosphere and lighting
- material direction
- context or site relationship when relevant

Avoid purely decorative mood images that do not show usable space.

## 6. Critic Guidance

Critic should evaluate:

- whether spatial logic and program are understandable
- whether scale and human use feel plausible
- whether material and light support the intended atmosphere
- whether site/context is addressed when the brief requires it
- whether outputs read as spatial design, not only abstract branding

## 7. Later Professional Deepening

Future work should add stronger references for:

- spatial typologies
- circulation and program diagrams
- architectural atmosphere precedents
- material-light relationships
- basic accessibility and public-space heuristics
