# Acceptance Criteria

## System consistency
- [ ] Every PNG uses only design_system palette tokens by name: `river-jade`, `stone-ink`, `wall-paper`, `lantern-gold`, `wood-brown`, `tile-mist`, `ginkgo-ochre`; no off-system substitute colors.
- [ ] Every deliverable names and visibly expresses the typography roles cited in the manifest (`display`, `headline`, `subhead`, `body`, `caption`, `mono`) rather than inventing a new type hierarchy.
- [ ] Every deliverable that needs auxiliary graphics uses `bridge-water-route` as defined in `design_system.motif_system.name`, including at least one of its listed components.
- [ ] The overall set reads as “地域文化感 + 收藏感 + 年轻传播性” within 2 seconds, using the system thesis and avoiding visual drift into generic Jiangnan or tech aesthetics.

## Non-duplication and reference grounding
- [ ] No deliverable replaces, redraws, or competes with the official mark; where the mark appears it must come from `official-logo` or `official-logo-footer` via image_edit.
- [ ] No deliverable directly reuses the official post-office product language: no `大清邮局复古邮政版式`, no `邮戳票据拼贴风`, no imperial postal insignia, no stamp/postmark styling.
- [ ] No scene application simply traces an official photo angle; edited scene work must show a transformed retail or merchandise context, not a photo repaint.
- [ ] Official naming is correct everywhere: `上海朱家角古镇` and `Zhujiajiao Ancient Town, Shanghai`.

## Merchandise-set completeness
- [ ] The PNG set forms a focused but complete tourism-retail system: hero posters, social cards, tote, badges, stickers/tags, postcard series, gift-box system, retail display, and a system moodboard are all present.
- [ ] At least one higher-ticket cultural gifting item is represented (`09-moodboard` gift-box system), and at least three impulse-buy tourism items are represented (tote, badge set, sticker/tag set, postcard set).
- [ ] The set demonstrates both day and night storytelling for Zhujiajiao, using `river-jade`, `lantern-gold`, `tile-mist`, and supporting imagery strategy from the design system.

## Visual quality and typography
- [ ] Bilingual text is baked into the pixels of each required communication piece and remains legible at normal gallery viewing size.
- [ ] Layouts follow the stated grid logic (`poster-portrait`, `square-card`, `landscape-banner`, `packaging-front-panel`) with clear hierarchy and whitespace.
- [ ] No AI clichés appear: no random gradients, no glowing nodes, no fake Latin text, no generic hex/brain/chip motifs, no universal red-lantern watercolor template.

## Deliverability
- [ ] `deliverable_manifest.json` lists 12 total items (`min_items = 12`) and every required PNG exists at the specified path and size family.
- [ ] `00-gallery.html` is the only HTML deliverable, is self-contained, and embeds every required PNG plus a concise design-system summary.
- [ ] All prompts used by Designer quote exact palette hexes from `design_system.json` and explicitly name the required typography roles and motif system.
