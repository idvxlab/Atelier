# Acceptance Criteria — Elderly AI Companion Device

## 1. System Consistency (design_system.json compliance)

- [ ] **Palette compliance**: Every PNG cites at least 3 tokens from `design_system.json::palette.tokens` by name or hex. Primary token `warm-shell` (#F2EDE8) appears as the dominant surface color in all product renders.
- [ ] **No forbidden colors**: No PNG contains pure black (#000000), cold blue-white, or high-saturation colors. All text uses `deep-pebble` (#5C5650), never pure black.
- [ ] **Form consistency**: The organic pebble silhouette is recognizable and consistent across all 8 PNGs. No sharp edges, no angular geometry, no cylindrical or spherical forms.
- [ ] **Breathing light motif**: `gentle-amber` (#E8C9A0) breathing light ring appears around the screen in all product renders (01, 02, 03, 04, 05). It is the only light-emitting element — no other glowing effects.
- [ ] **Fabric mesh zone**: `fabric-mist` (#C8C3BC) woven fabric texture is visible on the lower half of the device in all product renders.
- [ ] **Typography roles**: Screen UI text uses `display` role (large, ≥24pt equivalent, Noto Sans SC Medium). Board titles use `headline` role (Noto Serif SC). Annotations use `caption` role.
- [ ] **Material accuracy**: CMF board (06) correctly shows three distinct material textures — matte ceramic shell, soft-touch silicone, woven fabric mesh — matching `design_system.json::material_and_atmosphere`.

## 2. Non-Duplication (brand_lock.md compliance)

- [ ] **No ElliQ duplication**: No PNG shows a two-part head+body design, LED expression face, or segmented form.
- [ ] **No Echo/Nest duplication**: No PNG shows a cylindrical fabric-wrapped form or a perfect sphere.
- [ ] **No direct reference copying**: No PNG is visually similar to any research reference asset. References inspired the direction but the final design is original.
- [ ] **Each PNG is distinct**: 8 PNGs serve different purposes (hero, three-view, 2 scenes, detail, CMF, form language, scale) with no redundant compositions.

## 3. Requirement Coverage (brief compliance)

- [ ] **Organic form**: Product shape is clearly inspired by natural forms (pebble, water drop) — smooth, continuous curves, no sharp edges.
- [ ] **Neutral warm palette**: Color scheme is neutral gray-white with warm undertones, not cold or clinical.
- [ ] **Small screen + voice interaction**: Device has a visible small display screen and implies voice-first interaction.
- [ ] **Multi-scene portability**: At least 2 usage scenes (bedroom + living room) demonstrate the device moving between spaces.
- [ ] **Elderly-friendly design**: Detail view (05) shows large text, simple controls, anti-slip base — all accessibility requirements met.
- [ ] **Warm and approachable**: Overall impression is warm, safe, companion-like — NOT medical, NOT cold-tech.
- [ ] **Home integration**: Usage scenes show the device blending naturally into home decor, not standing out as technology.

## 4. Visual Quality

- [ ] **Rendering quality**: All PNGs are photorealistic or high-quality design presentation renders. No AI artifacts, no blurry details, no inconsistent lighting.
- [ ] **Lighting consistency**: Soft natural lighting (5000-5500K warm) across all renders. No harsh shadows, no strong reflections.
- [ ] **Composition**: Product hero (01) uses 3/4 elevated angle. Three-view (02) uses orthographic projection. Scenes use eye-level or slightly elevated. All compositions are intentional and professional.
- [ ] **Background treatment**: Hero and three-view use clean minimal backgrounds. Scenes use warm home environments. CMF and form boards use structured layouts.

## 5. Form Language Coherence

- [ ] **Pebble inspiration visible**: Form language board (07) clearly shows the evolution from natural pebble/drop shapes to the product form.
- [ ] **Continuous curvature**: All product views show continuous curvature changes — no flat截断, no geometric cuts.
- [ ] **Proportion lock**: Height-to-width ratio is approximately 1:1.3 across all product renders. Palm-sized scale confirmed in 08.
- [ ] **Screen placement**: Screen is consistently positioned in the upper 1/3 of the device, elliptical shape, across all views.

## 6. CMF Accuracy

- [ ] **Color tokens match**: CMF board swatches match the exact hex values from `design_system.json::palette.tokens`.
- [ ] **Material textures distinct**: Three material samples (matte ceramic, soft-touch silicone, woven fabric) are visually distinct and match `design_system.json::material_and_atmosphere::materials`.
- [ ] **Finish consistency**: All product renders show matte (not glossy) finishes. No metallic, chrome, or shiny surfaces.

## 7. Deliverability

- [ ] **File count**: Exactly 8 PNG files + 1 HTML gallery = 9 total deliverables.
- [ ] **File paths match manifest**: Each PNG file path matches `deliverable_manifest.json::deliverables[].file` exactly.
- [ ] **Gallery completeness**: `00-gallery.html` embeds all 8 PNGs, shows palette swatch row, shows type stack, groups by `deliverable_category`.
- [ ] **No extra files**: No SVG, no per-deliverable HTML, no separate token/typography files. Only the 8 PNGs + 1 gallery HTML.

## 8. Emotional Tone

- [ ] **Warmth**: Every product render evokes warmth and approachability within 2 seconds of viewing.
- [ ] **Dignity**: The device looks like a home decor object, not a medical device or assistive technology.
- [ ] **Companionship**: The breathing light motif creates a sense of "alive presence" — the device feels like a companion, not a tool.
- [ ] **Simplicity**: The overall design reads as simple and intuitive — an elderly user would not feel intimidated.
