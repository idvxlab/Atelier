# Task Breakdown — Elderly AI Companion Device

## Design System Decisions

### Domain & Mode
- **Domain**: `product_design` — consumer electronics / smart home companion device
- **Mode**: `speculative_concept` — original concept design, not extending an existing product
- **Style axis**: `warm-humanistic` (primary) + `craft-minimal` (secondary)

### Anchor Selection
- **Primary anchor**: `02-three-view` — locks the organic pebble silhouette, screen position, breathing light ring, fabric mesh zone, and overall proportions. All subsequent PNGs reference this form baseline.
- **Consistency lock**: The pebble-shaped organic form with warm-shell matte ceramic body, gentle-amber breathing light ring, and fabric-mist woven mesh must remain stable across all 8 PNGs.

### Expansion Decisions
- **Selected conditionals**:
  - `usage_scenario_render × 2` — brief explicitly requires multi-scene portability (bedroom + living room)
  - `detail_interaction_render` — brief emphasizes elderly-friendly design (large buttons/text/volume), needs dedicated detail view
  - `form_language_board` — product form is the core design differentiator (pebble inspiration), needs form evolution board
- **Omitted conditionals**:
  - `exploded_view` — internal structure not a design priority for this consumer product
  - `function_annotation_board` — core functions already shown in detail_interaction
  - `interaction_flow` — voice + simple touch interaction is straightforward, no complex flow needed
  - `packaging_display` — brief does not mention packaging or retail display

### Quantity Decision
- 8 PNGs + 1 gallery HTML = 9 total deliverables
- No explicit quantity signal in brief; this is a compact professional set covering all required product design categories

## Execution Order

### Phase 1: Form Definition (Priority: Critical)
| # | Task | Deliverable | Method | Notes |
|---|------|-------------|--------|-------|
| 1 | Generate hero product render | `01-hero-render.png` | `image_generate` | Establish the core form — organic pebble shape, warm-shell body, screen, breathing light, fabric mesh. This is the visual reference for all subsequent renders. |
| 2 | Generate three-view orthographic | `02-three-view.png` | `image_generate` | Lock the form baseline — front (screen + light ring), side (organic curve), top (overall shape). This becomes the consistency anchor. |

### Phase 2: Context & Scenes (Priority: High)
| # | Task | Deliverable | Method | Notes |
|---|------|-------------|--------|-------|
| 3 | Generate bedroom scene | `03-usage-scene-bedroom.png` | `image_generate` | Product on bedside table, warm morning light, home decor context. Reference: `senior-smart-home-hero` for environment atmosphere. |
| 4 | Generate living room scene | `04-usage-scene-livingroom.png` | `image_generate` | Product on coffee table/side cabinet, bright natural light, sofa + plants + tea set. Reference: `ikea-smart-home-minimal` for environment. |

### Phase 3: Detail & Systems (Priority: High)
| # | Task | Deliverable | Method | Notes |
|---|------|-------------|--------|-------|
| 5 | Generate detail/interaction view | `05-detail-interaction.png` | `image_generate` | Close-up showing screen UI (large Chinese text), touch buttons, breathing light detail, anti-slip base. Reference: `zco-companion-detail-1` for detail approach. |
| 6 | Generate CMF board | `06-cmf-board.png` | `image_generate` | Color swatches (4 tokens) + material samples (3 textures) + product detail. References: `ikea-dirigera-hub`, `soove-speaker-concept` for material approach. |
| 7 | Generate form language board | `07-form-language.png` | `image_generate` | Natural form inspiration (pebble, drop, shell) → silhouette evolution → final product form. Reference: `shell-speaker-form` for organic form approach. |

### Phase 4: Scale & Gallery (Priority: Medium)
| # | Task | Deliverable | Method | Notes |
|---|------|-------------|--------|-------|
| 8 | Generate scale reference | `08-scale-reference.png` | `image_generate` | Product in elderly person's hand, showing palm-sized scale and comfortable grip. |
| 9 | Build gallery HTML | `00-gallery.html` | `manual` | Embed all 8 PNGs, palette swatch row, type stack, grouped by deliverable_category. |

## Key Constraints for Designer

1. **Form consistency**: Every PNG must show the same organic pebble form. Use `02-three-view` as the form reference.
2. **Color tokens**: Quote exact hex values from `design_system.json` in every prompt. `warm-shell` (#F2EDE8) is always the dominant surface.
3. **Breathing light**: `gentle-amber` (#E8C9A0) ring around screen is the ONLY light-emitting element. Soft, warm, not bright.
4. **Fabric mesh**: `fabric-mist` (#C8C3BC) woven texture on lower half of device. Always visible in product renders.
5. **No forbidden elements**: Never use ElliQ two-part design, Echo cylinder, Nest sphere, pure black, cold white, sharp edges, medical device aesthetics, cyberpunk effects.
6. **Screen text**: Large Chinese text in `deep-pebble` (#5C5650) on `screen-glow` (#B8D4E3) background. Content: '今天天气很好 ☀', '该喝水了 💧', '女儿留言：周末回来看您'.
7. **Scene atmosphere**: Warm, natural, home-like. Product blends into decor. Not a tech showcase.
8. **Rendering style**: Photorealistic industrial design rendering. Soft natural lighting (5000-5500K). Muji/IKEA product photography aesthetic.

## Research Basis

| Finding | Source | Applied To |
|---------|--------|------------|
| Design for dignity — avoid medical appearance | ElliQ case study (fuseproject.com) | Overall design intent, all scenes |
| Natural organic forms — pebble/drop/shell | ZCO Design, Shell speaker (yankodesign) | Form language, hero render, three-view |
| Matte + fabric/silicone — warm tactile materials | Soove concept (yankodesign) | CMF board, material details |
| Voice-first + screen assist — large text, simple controls | Wirecutter senior smart home | Detail interaction, screen UI |
| Home integration — device as decor | IKEA smart home, senior smart home research | Usage scenes, atmosphere |

## Open Questions

These do not block execution but would refine the design if answered:

1. **Age segmentation**: Does the 65-75 vs 75-85 vs 85+ age range affect form factor, screen size, or button size?
2. **Health monitoring**: Should the device include health sensors (heart rate, blood pressure, fall detection)? This would affect form (sensor placement) and screen UI.
3. **Price positioning**: Premium (ceramic/metal accents) vs mid-range (quality plastic) vs entry-level (basic plastic)? This affects CMF decisions.
