# Acceptance Criteria — VibeFlow Creative Input Device

## System Consistency (Hard-Fail)

- [ ] All 7 PNG renders share the same 65% layout geometry: ~295mm wide × ~110mm deep × ~20mm thick, 12mm body corner radius
- [ ] Interaction zone placement is identical across all views: touch strip on left edge, rotary knob top-right, AI key cluster right of spacebar, magnetic expansion port on right edge
- [ ] Removable shell panel seam line visible in all product renders (2mm inset from edge)
- [ ] Keycap profile consistent: low-profile rounded cherry, matte top with subtle dish, 2mm corner radius
- [ ] Creative Coral colorway (coral #E8735A shell + amber #F5A623 knob + surface #F2EDE8 keycap area) used as default in hero, three-view, usage scene, interaction detail, exploded view
- [ ] All palette tokens cited from `design_system.json::palette.tokens` — no off-palette colors in any render
- [ ] Typography follows `design_system.json::typography.roles`: display for product name, caption for labels, annotation (monospace) for dimensions/specs

## Non-Duplication (Hard-Fail)

- [ ] No render duplicates competitor layouts: not Naya Connect's magnetic connector arrangement, not Clevetura CLVX1's 2×2 touch-on-keys, not DOIO KB16's triple-knob-plus-screen
- [ ] Each of the 7 PNGs has a distinct visual purpose and composition — no two images show the same angle or framing
- [ ] No generic AI clichés: no RGB rainbow lighting, no neural-net node clusters, no glowing hex patterns, no transparent case showing PCB

## Requirement Coverage

- [ ] **Hero render (01)**: 3/4 angle, full device visible, product name "VibeFlow" present, warm neutral background
- [ ] **Three-view (02)**: Front + Side + Top orthographic views, dimension annotations in monospace, magnetic expansion port visible in side view
- [ ] **Usage scene (03)**: Hands interacting with device, creative desk context (tablet/notebook/coffee), warm ambient lighting, no face visible
- [ ] **Interaction detail (04)**: Close-up of touch strip + rotary knob + AI key cluster, material contrast (matte vs gloss vs semi-transparent), labeled callouts
- [ ] **Exploded view (05)**: Layer separation showing removable shell, keycap plate, PCB, battery, magnetic expansion port module detached, guide lines, monospace annotations
- [ ] **CMF board (06)**: Three colorways (Creative Coral, Ocean Depth, Dream Lab), each with device thumbnail + color swatches + material notes
- [ ] **Form language board (07)**: Design element extraction (rounded geometry, gradient band, material contrast), interaction zone layout diagram, flow-curves motif

## Reference Grounding

- [ ] Product form informed by compact keyboard research (Keychron Q1, Lofree Block proportions) without copying
- [ ] Touch strip design informed by Clevetura CLVX1 reference but uses single strip (left edge) not 2×2 touch-on-keys
- [ ] Rotary knob design informed by DOIO KB16 but uses single knob (top-right) not triple-knob
- [ ] Modular expansion informed by Framework 16 but uses magnetic pogo-pin (right edge) not slide-rail
- [ ] Research assets used as style references only, not reproduced verbatim

## Visual Quality

- [ ] Studio renders: soft directional lighting from upper-left, gentle shadows, no harsh specular except on gloss elements
- [ ] Background: warm neutral (surface #F2EDE8 or light wood texture), never pure white (#FFFFFF) or pure black (#000000)
- [ ] Material rendering: clear distinction between matte body, gloss knob, semi-transparent touch strip
- [ ] No visible AI artifacts: no warped text, no impossible geometry, no floating elements, no inconsistent shadows

## Typography & Copy

- [ ] Product name "VibeFlow" rendered in geometric sans-serif bold (display role) — only in hero render and system boards
- [ ] Tagline "Express Intent" in caption weight — only in hero render
- [ ] Feature labels (Touch Strip, Dial, AI Keys) in caption role — in interaction detail
- [ ] Dimension/spec annotations in monospace (annotation role) — in three-view and exploded view
- [ ] CMF colorway names in caption role — in CMF board
- [ ] No text rendering errors: all text legible, no garbled characters, correct font weight

## Deliverability

- [ ] All 7 PNG files exist at paths specified in `deliverable_manifest.json`
- [ ] All PNGs are 1536×1024 pixels (landscape orientation)
- [ ] `00-gallery.html` exists at `artifacts/00-gallery.html`, embeds all 7 PNGs, inline CSS, no JS, no external assets
- [ ] Gallery includes palette swatch row and type stack callout from design_system.json
- [ ] Gallery presents PNGs grouped by deliverable_category with clear section headers

## Domain-Specific (Product Design)

- [ ] Product reads as a **compact input device for creative professionals** — not a gaming keyboard, not a generic macropad
- [ ] Multimodal interaction zones clearly identifiable: touch (strip), rotation (knob), press (AI keys), expansion (magnetic port)
- [ ] Portability conveyed: compact form factor, ~295mm width, lightweight appearance
- [ ] Creative vitality expressed through color (coral/amber gradient), rounded geometry, material warmth — not through RGB lighting or aggressive styling
- [ ] Modular concept clear: removable shell panels, magnetic expansion port visible in exploded view
