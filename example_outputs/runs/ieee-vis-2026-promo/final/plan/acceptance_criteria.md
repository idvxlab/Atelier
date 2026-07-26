# IEEE VIS 2026 Promotional Visual System — Acceptance Criteria

## System Consistency (Critical)

- [ ] All 11 PNG deliverables use dark backgrounds (ink `#0A0A0F` or surface `#1A1A24`) — no light backgrounds anywhere
- [ ] All deliverables cite palette tokens from `design_system.json` by name or hex value
- [ ] Space Grotesk used for all display and headline text across all deliverables
- [ ] Inter used for all body and caption text across all deliverables
- [ ] JetBrains Mono used only for technical/data accent elements (if present)
- [ ] Accent colors limited to primary `#00D4FF`, accent-warm `#FF4D6A`, accent-cool `#6366F1` — no more than 3 accent colors per composition
- [ ] All geometric forms are abstract and original — not a pixel-for-pixel copy of the hex-pattern-texture reference
- [ ] 8px grid alignment visible or implied in all compositions
- [ ] High contrast maintained: text-primary `#FFFFFF` on dark backgrounds, minimum WCAG AA contrast ratio

## Non-Duplication (Critical)

- [ ] IEEE VIS 2026 official logo appears on all deliverables — not recreated, not modified
- [ ] IEEE master brand logo appears per IEEE brand guidelines — not recreated
- [ ] IEEE VGTC logo appears as co-organizer — not recreated
- [ ] Past conference logos (VIS 2024, VIS 2025) do not appear in any deliverable
- [ ] The exact hex-pattern-texture from the website is not copied — only referenced as aesthetic inspiration
- [ ] No generic AI clichés: gradient blobs, glowing nodes, abstract tech circles, brain motifs

## Requirement Coverage (Critical)

- [ ] A2 main poster (01) includes: IEEE VIS 2026 name, dates November 9–13 2026, location Boston Massachusetts, all three logos, tagline or positioning statement
- [ ] Key visual (02) works as standalone campaign image with conference name and visual identity
- [ ] Typography board (03) demonstrates all 5 type roles: display, headline, body, caption, data
- [ ] Color/visual rules board (04) shows all 8 palette tokens with hex values and geometric motif examples
- [ ] Twitter post (05) is 1200×675 aspect ratio with conference info and logos
- [ ] Twitter header (06) is 1500×500 aspect ratio, wide banner format
- [ ] LinkedIn post (07) is 1200×627 aspect ratio with professional tone
- [ ] Instagram post (08) is 1080×1080 square format
- [ ] Instagram story (09) is 1080×1920 vertical 9:16 format
- [ ] Badge/lanyard (10) shows badge mockup with logo, name placeholder, dates, and lanyard design
- [ ] PPT template (11) shows both title slide and content slide in one composite image
- [ ] All text is in English only — no Chinese characters in any deliverable

## Reference Grounding (High)

- [ ] Swiss/International Typographic Style precedents (swiss-style-poster-turnfest, swiss-style-poster-pkz) inform the geometric composition and typography approach
- [ ] Hex-pattern-texture referenced as motif inspiration but not copied exactly
- [ ] IEEE VIS 2024 swag referenced for badge/lanyard application context
- [ ] IEEE VIS 2025 isotypes referenced for systematic multi-touchpoint identity approach
- [ ] Boston skyline context optionally referenced but not dominant

## Visual Quality (High)

- [ ] Main poster has clear visual hierarchy: conference name seen first, dates/location second, supporting info third
- [ ] Geometric compositions are intentional and grid-based, not random decorative elements
- [ ] Typography is legible at intended viewing distances (poster: 2m+, social: arm's length, badge: 0.5m)
- [ ] Color contrast is sufficient for readability in all formats
- [ ] No visual clutter — whitespace is intentional, not accidental
- [ ] Geometric forms suggest data visualization without being literal charts or graphs

## Typography (High)

- [ ] Display type (Space Grotesk Bold) is oversized and commanding on poster and key visual
- [ ] Headline type (Space Grotesk SemiBold) is clearly secondary to display but still bold
- [ ] Body type (Inter Regular) is clean and readable at small sizes
- [ ] Caption type (Inter Regular, smaller) maintains readability
- [ ] Data type (JetBrains Mono) used sparingly for technical accent only
- [ ] Type scale follows 1.25 modular ratio across all deliverables
- [ ] Tracking and leading are appropriate for each type role

## Deliverability (High)

- [ ] All PNG files are named according to manifest: `01-main-poster.png` through `11-ppt-template.png`
- [ ] All PNG files are in `artifacts/generated-images/` directory
- [ ] Gallery HTML (`00-gallery.html`) embeds all 11 PNGs in a primary Final Deliverables section
- [ ] Gallery HTML includes palette swatch row showing all 8 tokens with hex values
- [ ] Gallery HTML includes type stack callout showing all 5 type roles
- [ ] Gallery HTML is self-contained: inline CSS, no JS, no external assets
- [ ] Gallery HTML shows reference assets in a secondary Reference Library section
- [ ] Badge design is legible at physical 100×70mm size
- [ ] PPT template shows both title and content slides clearly

## Message Hierarchy (Medium)

- [ ] Main poster communicates "IEEE VIS 2026" within 2 seconds of viewing
- [ ] Dates and location are clearly visible and readable
- [ ] Logo lockup order is correct: IEEE (master brand) → VIS 2026 (conference) → VGTC (co-organizer)
- [ ] Social media posts communicate conference name and dates at social scroll speed
- [ ] Badge communicates conference identity and attendee info at arm's length

## Format Adaptation (Medium)

- [ ] All 5 social media formats maintain the same visual idea despite different aspect ratios
- [ ] Geometric composition adapts to each format without losing the core visual identity
- [ ] Typography scales appropriately for each format (poster: 120-180pt display, social: 48-72pt display, badge: 24-36pt display)
- [ ] Logo lockup adapts to each format while maintaining correct order and clear space
- [ ] Wide formats (Twitter header) use horizontal geometric composition
- [ ] Square formats (Instagram post) use centered or balanced composition
- [ ] Vertical formats (Instagram story) stack information vertically

## Professional Tone (Medium)

- [ ] Visual tone is professional, academic, and innovative — not playful or casual
- [ ] Design respects the academic audience (researchers, scholars, practitioners)
- [ ] No stock photography or people imagery
- [ ] Geometric forms are abstract and sophisticated, not cartoonish or decorative
- [ ] Color palette is high-contrast and bold but not garish or overwhelming

## Copy Accuracy (Medium)

- [ ] Conference name is "IEEE VIS 2026" (not "IEEE Visualization 2026" or other variations)
- [ ] Dates are "November 9–13, 2026" (with en-dash, not hyphen)
- [ ] Location is "Boston, Massachusetts" (not just "Boston" or "Boston, MA" on poster)
- [ ] Tagline references official positioning: "The Premier Forum for Visualization" or similar
- [ ] Six research areas mentioned if space allows (Theoretical & Empirical, Applications, Systems & Rendering, Representations & Interaction, Data Transformations, Analytics & Decisions)

## Accessibility (Low)

- [ ] Text is legible against dark backgrounds (minimum WCAG AA contrast)
- [ ] Badge design considers readability at physical size for attendees with visual impairments
- [ ] Color is not the only means of conveying information (text labels accompany color-coded elements)

## Open Questions (Informational)

- [ ] If color palette strictly follows existing IEEE VIS 2026 website, document the mapping
- [ ] If specific conference theme/tagline exists beyond general positioning, incorporate it
- [ ] If mandatory elements (sponsor logos, accessibility requirements) exist, include them
- [ ] If A2 poster has specific display context (venue, universities, digital), optimize for that context
