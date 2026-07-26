# IEEE VIS 2026 Promotional Visual System — Task Breakdown

## Overview

This task breakdown guides the Designer through creating 11 PNG deliverables plus one gallery HTML for the IEEE VIS 2026 promotional visual system. The design system is defined in `plan/design_system.json`. The A2 main poster is the consistency anchor — all other deliverables adapt its visual idea.

**Design mode**: Extension — extend existing IEEE VIS 2026 identity across all deliverables.

**Style direction**: Swiss/International Typographic Style — grid-based, bold geometric forms, strong contrast, expressive sans-serif typography.

**Key constraints**:
- All text in English only
- Dark backgrounds only (ink #0A0A0F or surface #1A1A24)
- Official logos (IEEE, VIS 2026, VGTC) must not be recreated — use official files
- Geometric forms must be abstract and original — do not copy hex-pattern-texture exactly
- Max 3 accent colors per composition

---

## Phase 1: Foundation (Priority: Critical)

### Task 1.1: Establish the Visual Anchor — Main Poster
**Priority**: P0 (Critical)
**Deliverable**: `01-main-poster.png` (A2 portrait, 1024×1792)
**Method**: `image_generate`
**Reference assets**: `swiss-style-poster-pkz`, `swiss-style-poster-turnfest`

**Objective**: Create the A2 main poster that establishes the complete visual system. This is the consistency anchor for all other deliverables.

**Requirements**:
- Dark background: ink `#0A0A0F`
- Bold oversized "IEEE VIS 2026" in Space Grotesk Bold white text, dominating upper third
- Below: "November 9–13, 2026" and "Boston, Massachusetts" in clean hierarchy
- Abstract geometric composition: bold rectangles, circles, angular forms in bright cyan `#00D4FF`, coral-pink `#FF4D6A`, indigo `#6366F1`
- Geometric forms arranged on visible 12-column grid
- Forms suggest data visualization without being literal charts
- IEEE logo top-left, VGTC logo bottom-right
- Tagline "The Premier Forum for Visualization" as secondary text
- High contrast, clean edges, no gradients, no shadows
- Professional academic tone with visual impact

**Prompt seed**: "A2 portrait conference poster, Swiss/International Typographic Style. Dark near-black background (#0A0A0F). Bold oversized 'IEEE VIS 2026' in Space Grotesk Bold white text, dominating upper third. Below: 'November 9–13, 2026' and 'Boston, Massachusetts' in clean hierarchy. Abstract geometric composition: bold rectangles, circles, and angular forms in bright cyan (#00D4FF), coral-pink (#FF4D6A), and indigo (#6366F1) arranged on a visible 12-column grid. Geometric forms suggest data visualization without being literal charts. IEEE logo top-left, VGTC logo bottom-right. Tagline 'The Premier Forum for Visualization' as secondary text. High contrast, clean edges, no gradients, no shadows. Professional academic tone with visual impact."

**Negative prompt**: "Light background, serif fonts, gradients, drop shadows, 3D effects, stock photography, people, literal charts or graphs, generic tech circles, glowing nodes, AI clichés, Chinese text, decorative elements without purpose"

**Acceptance test**: Dark ink background, bold geometric composition in accent colors, oversized Space Grotesk 'IEEE VIS 2026', dates Nov 9-13 2026, Boston MA, all three logos in correct lockup, 8px grid alignment visible.

**Dependencies**: None — this is the anchor.

**Notes**: Study the Swiss style precedent posters for geometric composition and typography approach. The poster should feel academic and professional while having strong visual impact. The geometric forms should be the visual hook — they suggest data/visualization without being literal.

---

### Task 1.2: Create the Key Visual / Master Visual
**Priority**: P0 (Critical)
**Deliverable**: `02-key-visual.png` (Square, 1024×1024)
**Method**: `image_generate`
**Reference assets**: `hex-pattern-texture`

**Objective**: Create a square key visual that works as the campaign seed. This proves the visual idea works as a standalone master visual before adaptation to other formats.

**Requirements**:
- Dark background: ink `#0A0A0F`
- Bold abstract geometric composition: overlapping hexagonal-inspired shapes, network-like node connections, color blocks in cyan `#00D4FF`, coral `#FF4D6A`, indigo `#6366F1`
- "IEEE VIS 2026" in large Space Grotesk Bold white text
- Geometric forms are original, inspired by data visualization aesthetics
- Clean, high-contrast, no gradients
- Swiss style grid-based composition
- Professional and innovative tone

**Prompt seed**: "Square key visual / master visual for IEEE VIS 2026 conference campaign. Dark background (#0A0A0F). Bold abstract geometric composition: overlapping hexagonal-inspired shapes, network-like node connections, and color blocks in cyan (#00D4FF), coral (#FF4D6A), and indigo (#6366F1). 'IEEE VIS 2026' in large Space Grotesk Bold white text. Geometric forms are original, inspired by data visualization aesthetics. Clean, high-contrast, no gradients. Swiss style grid-based composition. Professional and innovative."

**Negative prompt**: "Light background, literal hex pattern copy, stock photos, people, gradients, shadows, generic tech imagery, AI clichés"

**Acceptance test**: Same visual language as poster in square format. Geometric forms, bold typography, dark background, accent colors. Works as standalone campaign image.

**Dependencies**: Task 1.1 (main poster) — adapt the same visual idea to square format.

**Notes**: The key visual can focus more on the geometric composition and less on information density. It should work as a standalone image for campaign use.

---

## Phase 2: System Documentation (Priority: High)

### Task 2.1: Typography Hierarchy Board
**Priority**: P1 (High)
**Deliverable**: `03-typography-hierarchy-board.png` (Portrait, 1024×1792)
**Method**: `image_generate`
**Reference assets**: None

**Objective**: Create a typography system board that demonstrates the complete type hierarchy across all roles.

**Requirements**:
- Dark background: ink `#0A0A0F`
- Show all 5 type roles:
  - Display: "IEEE VIS 2026" in Space Grotesk Bold, massive size (120-180pt equivalent)
  - Headline: "November 9–13, 2026 · Boston, Massachusetts" in Space Grotesk SemiBold
  - Body: Paragraph of text in Inter Regular explaining the conference
  - Caption: Small text in Inter Regular, text-secondary color `#B0B0C0`
  - Data: "DATA_VIZ_2026" or similar in JetBrains Mono
- Each level labeled with role name, typeface, weight, and size
- Clean grid layout, white and gray text on dark
- Systematic, professional, academic

**Prompt seed**: "Typography system specification board on dark background (#0A0A0F). Shows the complete type hierarchy: 'IEEE VIS 2026' in massive Space Grotesk Bold (display role), 'November 9–13, 2026 · Boston' in Space Grotesk SemiBold (headline role), body text paragraph in Inter Regular (body role), small caption text in Inter (caption role), and 'DATA_VIZ_2026' in JetBrains Mono (data role). Each level labeled with role name, typeface, weight, and size. Clean grid layout, white and gray text on dark. Systematic, professional, academic."

**Negative prompt**: "Light background, serif fonts, decorative elements, colorful backgrounds, messy layout, inconsistent spacing"

**Acceptance test**: Shows Space Grotesk display/headline, Inter body/caption, JetBrains Mono data. Clear hierarchy from display to caption. Dark background. All type roles labeled.

**Dependencies**: None — can be created in parallel with Phase 1.

**Notes**: This board documents the type system for the gallery and for reference. It should be clear and systematic.

---

### Task 2.2: Color and Visual Rules Board
**Priority**: P1 (High)
**Deliverable**: `04-color-visual-rules-board.png` (Portrait, 1024×1792)
**Method**: `image_generate`
**Reference assets**: `hex-pattern-texture`

**Objective**: Create a color palette and visual rules board that documents the system for cross-format consistency.

**Requirements**:
- Dark background: ink `#0A0A0F`
- Show all 8 palette tokens as swatches with hex values:
  - ink `#0A0A0F`, surface `#1A1A24`, primary `#00D4FF`, accent-warm `#FF4D6A`
  - accent-cool `#6366F1`, text-primary `#FFFFFF`, text-secondary `#B0B0C0`, grid-line `#2A2A36`
- Show geometric motif examples (abstract hexagonal clusters, network nodes, geometric color blocks)
- Show format adaptation logic (how the system scales from poster to social to badge)
- Clean, systematic layout
- Professional and academic tone

**Prompt seed**: "Color palette and visual rules specification board on dark background (#0A0A0F). Top section: 8 color swatches in a row showing ink (#0A0A0F), surface (#1A1A24), primary cyan (#00D4FF), accent-warm coral (#FF4D6A), accent-cool indigo (#6366F1), text-primary white (#FFFFFF), text-secondary gray (#B0B0C0), grid-line (#2A2A36). Each swatch labeled with token name and hex value. Middle section: geometric motif examples — abstract hexagonal clusters, network node diagrams, geometric color blocks in accent colors. Bottom section: format adaptation diagram showing how the visual system scales from A2 poster to social media to badge. Clean grid layout, systematic, professional."

**Negative prompt**: "Light background, messy layout, inconsistent spacing, decorative elements without purpose, gradients"

**Acceptance test**: Shows all 8 palette tokens as swatches with hex values. Shows geometric motif examples. Shows format adaptation logic. Dark background. Systematic layout.

**Dependencies**: None — can be created in parallel with Phase 1.

**Notes**: This board documents the visual system for the gallery and for reference. It should be clear and systematic.


---

## Phase 3: Social Media Adaptations (Priority: High)

### Task 3.1: Twitter/X Post
**Priority**: P1 (High)
**Deliverable**: `05-social-twitter-post.png` (1200×675, 1792×1024)
**Method**: `image_generate`

Adapt the visual system to Twitter/X post format (16:9 landscape). Dark background, geometric composition, bold Space Grotesk type, dates and location visible, logos present. Same visual language as main poster. Readable at social media scroll size.

### Task 3.2: Twitter/X Header
**Priority**: P1 (High)
**Deliverable**: `06-social-twitter-header.png` (1500×500, 1792×1024)
**Method**: `image_generate`

Wide 3:1 horizontal banner for Twitter/X profile header. Geometric composition spanning full width. Conference name prominent. Logos visible.

### Task 3.3: LinkedIn Post
**Priority**: P1 (High)
**Deliverable**: `07-social-linkedin-post.png` (1200×627, 1792×1024)
**Method**: `image_generate`

LinkedIn post format. Same visual system as Twitter post with slightly different aspect ratio. Professional tone for LinkedIn audience.

### Task 3.4: Instagram Post
**Priority**: P1 (High)
**Deliverable**: `08-social-instagram-post.png` (1080×1080, 1024×1024)
**Method**: `image_generate`

Square format. Bold geometric composition centered. Conference name dominant. Accent colors. Balanced square composition.

### Task 3.5: Instagram Story
**Priority**: P1 (High)
**Deliverable**: `09-social-instagram-story.png` (1080×1920, 1024×1792)
**Method**: `image_generate`

Vertical 9:16 format. Geometric forms adapted to tall format. Conference info stacked vertically. Full-screen story composition.

---

## Phase 4: Application Deliverables (Priority: High)

### Task 4.1: Conference Badge and Lanyard
**Priority**: P1 (High)
**Deliverable**: `10-badge-lanyard.png` (100×70mm badge + lanyard, 1792×1024)
**Method**: `image_generate`
**Reference assets**: `ieee-vis-2024-swag`

Badge: dark background, IEEE VIS 2026 logo, attendee name placeholder, dates, role label. Lanyard: accent color with repeating pattern or text. Logos legible at small physical size. Mockup showing badge + lanyard together.

### Task 4.2: PPT/Keynote Template
**Priority**: P1 (High)
**Deliverable**: `11-ppt-template.png` (16:9, 1792×1024)
**Method**: `image_generate`

Two slides shown: title slide with full conference info and geometric background, content slide with clean layout and subtle geometric accent. Dark backgrounds, consistent typography, logos on title slide.

---

## Phase 5: Gallery (Priority: Medium)

### Task 5.1: Create Gallery HTML
**Priority**: P2 (Medium)
**Deliverable**: `00-gallery.html`
**Method**: `manual`

Single polished self-contained HTML page. Embeds all 11 PNGs grouped by deliverable_category. Inline CSS, no JS, no external assets. Palette swatch row and type stack callout at top. Reference Library section for research provenance. Dark background matching design system.

---

## Conditional Outputs — Selection Rationale

### Selected Conditionals

1. **Key visual (02-key-visual)**: The brief asks for a "promotional visual system." The key visual is the campaign seed that proves the visual idea works standalone before adaptation. Essential for multi-format campaigns.

2. **Typography hierarchy board (03)**: The brief emphasizes "bold typography" as a core style element. A dedicated board proves the type system works across sizes and documents it for the gallery.

3. **Color and visual rules board (04)**: Multi-format deliverables (poster + 5 social sizes + badge + PPT) require explicit color and visual rules to ensure consistency. The board documents the system.

### Omitted Conditionals

1. **Banner/horizontal adaptation**: Twitter header (1500×500) already covers the wide horizontal format. No separate banner needed.

2. **Poster series variation**: Brief asks for one main poster. No multiple campaign phases or poster series requested.

3. **Media placement mockup**: Brief focuses on the deliverables themselves, not their display context. Placement mockups would add scope without brief justification.

4. **Campaign asset overview board**: The color/visual rules board and typography board together document the system. A separate overview board would be redundant.

---

## Execution Order Summary

| Order | Task | Priority | Dependencies |
|-------|------|----------|--------------|
| 1 | 01-main-poster | P0 | None (anchor) |
| 2 | 02-key-visual | P0 | Task 1 |
| 3 | 03-typography-board | P1 | None (parallel) |
| 4 | 04-color-rules-board | P1 | None (parallel) |
| 5 | 05-twitter-post | P1 | Task 1 |
| 6 | 06-twitter-header | P1 | Task 1 |
| 7 | 07-linkedin-post | P1 | Task 1 |
| 8 | 08-instagram-post | P1 | Task 1 |
| 9 | 09-instagram-story | P1 | Task 1 |
| 10 | 10-badge-lanyard | P1 | Task 1 |
| 11 | 11-ppt-template | P1 | Task 1 |
| 12 | 00-gallery.html | P2 | All above |

Tasks 3-4 can run in parallel with Tasks 1-2. Tasks 5-11 can run in parallel after Task 1 is complete. Task 12 (gallery) runs last after all PNGs are complete.
