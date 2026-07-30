# Task Breakdown — VibeFlow Creative Input Device

## Overview

This plan produces **7 PNG renders + 1 gallery HTML** for a speculative compact input device concept ("VibeFlow") targeting creative professionals in the VibeCoding paradigm. All renders share a consistent 65% layout geometry and Creative Coral colorway as the anchor.

---

## Task Sequence

### Phase 1: Anchor Lock (Priority: CRITICAL)

**Task 1.1 — Generate 02-three-view.png**
- **Priority**: P0 (must be done first — this is the geometric anchor)
- **Method**: `image_generate`
- **Purpose**: Establish the canonical orthographic geometry that all subsequent renders must match.
- **Key constraints**:
  - 295mm wide × 110mm deep × 20mm thick, 12mm body corner radius
  - Front view: 65% keycap layout, touch strip left edge, rotary knob top-right, AI key cluster right of spacebar
  - Side view: 20mm thickness profile, magnetic expansion port on right edge with pogo-pin contacts
  - Top view: full layout from above
  - Creative Coral colorway: coral #E8735A shell, amber #F5A623 knob, surface #F2EDE8 keycap area
  - Dimension annotations in monospace (annotation role)
- **Acceptance**: Three clean orthographic views with consistent geometry, labeled Front/Side/Top, dimension callouts visible.

---

### Phase 2: Hero & Context (Priority: HIGH)

**Task 2.1 — Generate 01-hero-render.png**
- **Priority**: P1
- **Method**: `image_generate`
- **Purpose**: Primary product visual — 3/4 angle hero shot.
- **Key constraints**:
  - 3/4 angle from front-left, showing rounded body, all interaction zones visible
  - Creative Coral colorway (coral shell, amber knob, surface keycap area)
  - Product name "VibeFlow" in display font + tagline "Express Intent" in caption font
  - Warm neutral background (surface #F2EDE8)
  - Soft directional lighting from upper-left
- **Reference**: Use 02-three-view as geometry guide.
- **Acceptance**: Compelling hero image, product name legible, all design-system tokens cited.

**Task 2.2 — Generate 03-usage-scene.png**
- **Priority**: P1
- **Method**: `image_generate`
- **Reference asset**: `multiple-input-devices-setup` (for desk context composition)
- **Purpose**: Lifestyle context showing hands using the device in a creative workspace.
- **Key constraints**:
  - Hands interacting with touch strip or rotary knob (no face visible)
  - Desk context: design tablet, coffee cup, notebook with sketches
  - Warm ambient lighting, shallow depth of field
  - Creative Coral colorway visible
- **Acceptance**: Conveys creative flow, multimodal interaction, warm professional environment.

---

### Phase 3: Detail & Structure (Priority: HIGH)

**Task 3.1 — Generate 04-interaction-detail.png**
- **Priority**: P1
- **Method**: `image_generate`
- **Reference assets**: `clevetura-clvx1-touch-keyboard` (touch strip style), `doio-kb16-triple-knob-macropad` (knob style)
- **Purpose**: Close-up showing the three multimodal interaction zones and material contrast.
- **Key constraints**:
  - Three areas visible: semi-transparent touch strip (left), glossy amber knob (top-right), AI key cluster with coral accent (right of spacebar)
  - Material contrast: matte graphite body vs gloss-white knob vs semi-transparent touch zone
  - Labels: "Touch Strip", "Dial", "AI Keys" in caption font
  - Shallow depth of field, studio lighting
- **Acceptance**: Clear material differentiation, labeled callouts, no full device visible.

**Task 3.2 — Generate 05-exploded-view.png**
- **Priority**: P1
- **Method**: `image_generate`
- **Reference asset**: `framework-numpad-module` (modular connector style)
- **Purpose**: Technical exploded view showing modular structure.
- **Key constraints**:
  - Layers separated vertically: removable shell → keycap plate → PCB → battery/bottom case
  - Magnetic expansion port module detached to the right with pogo-pin contacts visible
  - Guide lines connecting mating surfaces
  - Annotations in monospace: "Removable Shell", "Magnetic Pogo-Pin", "Expansion Port", "Touch Strip Module"
  - Clean technical style on surface background
- **Acceptance**: Modular concept clear, all layers identifiable, pogo-pin connector visible.

---

### Phase 4: System Boards (Priority: MEDIUM)

**Task 4.1 — Generate 06-cmf-board.png**
- **Priority**: P2
- **Method**: `image_generate`
- **Purpose**: CMF presentation showing three colorway options.
- **Key constraints**:
  - Three colorways in a row, each with device thumbnail + color swatches + material notes:
    1. **Creative Coral**: coral #E8735A shell + amber #F5A623 knob + surface #F2EDE8 keycaps (matte+gloss mix)
    2. **Ocean Depth**: teal #2A7B88 shell + gloss-white #FAFAF7 knob + surface keycaps (cool matte)
    3. **Dream Lab**: lavender #B8A9D4 shell + coral #E8735A knob + graphite #4A464D keycaps (soft-touch)
  - Title "CMF Options" in display font, labels in caption font
  - Clean board layout on surface #F2EDE8 background
- **Acceptance**: Three distinct colorways clearly differentiated, swatches match design-system tokens.

**Task 4.2 — Generate 07-form-language.png**
- **Priority**: P2
- **Method**: `image_generate`
- **Purpose**: Design language board showing form evolution and design principles.
- **Key constraints**:
  - Left column: design element extraction — rounded rectangle geometry (12mm radius), coral→amber gradient band, matte-vs-gloss material contrast diagram
  - Right column: interaction zone layout diagram — touch strip (left), rotary knob (top-right), AI key cluster (right of spacebar), magnetic expansion port (right edge)
  - Center: product in Creative Coral colorway
  - Title "Design Language" in display font, annotations in monospace
  - Flow-curves motif throughout
- **Acceptance**: Design rationale clear, flow-curves motif visible, interaction zones mapped.

---

### Phase 5: Gallery (Priority: MEDIUM)

**Task 5.1 — Build 00-gallery.html**
- **Priority**: P2
- **Method**: `manual`
- **Purpose**: Single self-contained HTML page presenting all 7 PNGs + design system context.
- **Key constraints**:
  - Inline CSS only, no JS, no external assets
  - Palette swatch row at top (all 8 tokens from design_system.json)
  - Type stack callout (display, caption, annotation, body roles)
  - PNGs grouped by deliverable_category with section headers
  - Optional: Reference Library section showing research assets with attribution
  - File paths must match deliverable_manifest.json exactly
- **Acceptance**: Renders correctly in browser, all 7 PNGs embedded, design system context visible.

---

## Conditional Outputs — Selection Rationale

### Selected expansions:
| Deliverable | Reason |
|---|---|
| Exploded view (05) | Brief explicitly requires modular expansion design; exploded view is the clearest way to show removable shell, magnetic pogo-pin, and internal structure |
| CMF board (06) | Brief emphasizes "多彩配色、可更换外壳" — three colorways need dedicated presentation |
| Interaction detail (04) | Multimodal interaction (touch + rotary + AI keys) is the core differentiator; close-up proves the concept |
| Usage scene (03) | Brief targets "桌面/移动/共享空间多场景"; lifestyle context validates portability and creative positioning |
| Form language board (07) | Concept design stage requires showing design rationale and form evolution |

### Omitted expansions:
| Category | Reason |
|---|---|
| Interaction flow diagram | Better suited to UI/UX design; the interaction detail close-up already communicates multimodal concept |
| Packaging/display mockup | Brief does not mention packaging or retail; concept stage should focus on the product itself |
| Scale reference (hand-only) | Usage scene already includes hands for scale; a separate scale shot would be redundant |

---

## Key Design Decisions (Recorded for Traceability)

1. **Product name**: "VibeFlow" — coined from VibeCoding + creative flow state. Speculative, not a real brand.
2. **Form factor**: 65% layout (~295×110×20mm) — balances compactness with enough room for interaction zones.
3. **Interaction zone layout**: Touch strip left edge (thumb glide), rotary knob top-right (index finger), AI key cluster right of spacebar (right thumb), magnetic expansion port right edge.
4. **Modular interface**: Magnetic pogo-pin — convenient for concept stage, no slide-rail mechanism needed.
5. **CMF strategy**: 3 colorways (Creative Coral / Ocean Depth / Dream Lab) — coral as hero, teal and lavender as alternatives.
6. **Keycap profile**: Low-profile rounded cherry, matte top with subtle dish — comfortable for long creative sessions.
7. **Design language**: "Flow-curves" — rounded geometry, gradient transitions, matte/gloss contrast. No RGB, no gaming aesthetics.

---

## Execution Notes for Designer

- **Always reference 02-three-view.png** as the geometric anchor when generating subsequent renders.
- **Maintain consistent interaction zone placement** across all views — this is the product's signature.
- **Use warm neutral backgrounds** (surface #F2EDE8 or light wood) — never pure white or pure black.
- **Cite palette tokens by hex** in every image prompt (e.g., "coral #E8735A", not just "coral").
- **Product name "VibeFlow" appears only in hero render and system boards** — not in usage scenes or detail shots.
- **All text must use the correct typography role**: display for product name, caption for labels, annotation (monospace) for dimensions.
