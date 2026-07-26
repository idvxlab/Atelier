# 任务分解 — 京剧脸谱国潮文创系列

> 按优先级排序。Designer 必须按此顺序执行。
> 依赖关系：设计规格板 → 产品图 → Gallery 页面。

---

## Phase 0: 设计规格板（必须先生成，作为后续产物的视觉锚点）

### Task 0.1 — 文化色板规格板 `cultural-palette.png`
- **优先级**: P0（最高）
- **依赖**: 无
- **方法**: image_generate
- **内容**: 展示京剧脸谱色彩象征体系（红=忠义、黑=刚直、白=智谋、蓝=刚强、金银=神仙）与品牌色板的对照关系。7 个 palette token 的色块 + 色值 + 文化含义标注。
- **验收**: 7 个色值与 design_system.palette.tokens 完全一致；每个色块标注文化含义；排版清晰可读。

### Task 0.2 — 材料工艺规格板 `material-board.png`
- **优先级**: P0
- **依赖**: 无
- **方法**: image_generate
- **内容**: 展示产品线使用的材料工艺——珐琅徽章（金属边框+色块填充）、陶瓷杯（釉面质感）、特种纸包装（纸张纹理）。每种材料配实物参考。
- **验收**: 3 种材料质感清晰可辨；与 research/evidence.json 中的材料工艺参考一致。

### Task 0.3 — 纹样系统规格板 `iconography.png`
- **优先级**: P0
- **依赖**: 无
- **方法**: image_generate
- **内容**: 展示「脸谱解构纹样 / Deconstructed Lianpu Patterns」motif 系统——额头图案解构、眼窝造型、脸谱轮廓线、装饰纹样（云纹/火焰纹/蝙蝠纹）、色块分割。每个元素配使用示例。
- **验收**: 5 类纹样元素全部展示；保持脸谱对称性；粗轮廓线风格一致。

---

## Phase 1: 核心产品图（P0 — 定义系列视觉基调）

### Task 1.1 — 产品系列总览 `01-product-overview.png`
- **优先级**: P0
- **依赖**: Task 0.1-0.3（规格板完成后开始）
- **方法**: image_generate
- **内容**: 徽章、杯子、纪念品三大品类的整体视觉效果展示。品牌名「脸谱潮 / LIANPU CHAO」清晰可见。
- **验收**: 产品排列有节奏感；使用 cinnabar-red / gold-leaf / ink-black / rice-paper 四色；品牌名清晰。

### Task 1.2 — 忠义红系列 `02-product-variant-01.png`
- **优先级**: P0
- **依赖**: Task 0.1-0.3
- **方法**: image_generate
- **内容**: 关羽红脸主题——徽章+杯子组合。cinnabar-red #e8433f 为主色。
- **验收**: 关羽红脸纹样清晰可辨；珐琅/陶瓷质感可感知；gold-leaf 点缀。

### Task 1.3 — 刚直黑系列 `03-product-variant-02.png`
- **优先级**: P0
- **依赖**: Task 0.1-0.3
- **方法**: image_generate
- **内容**: 包拯黑脸主题——徽章+纪念品组合。ink-black #1a1a2e 为主色。
- **验收**: 包拯月牙纹样为核心；金色点缀体现品质感。

---

## Phase 2: 场景与细节图（P1 — 丰富产品线展示）

### Task 2.1 — 文化场景图 `04-cultural-context.png`
- **优先级**: P1
- **依赖**: Task 1.1-1.3
- **方法**: image_generate
- **内容**: 产品在年轻人日常生活中的使用场景。
- **验收**: 场景自然不做作；体现 Z 世代审美。

### Task 2.2 — 工艺细节特写 `05-detail-closeup.png`
- **优先级**: P1
- **依赖**: Task 1.1-1.3
- **方法**: image_generate
- **内容**: 珐琅徽章精细工艺和脸谱纹样细节。
- **验收**: 纹样细节清晰；珐琅质感真实；体现 motif 系统。

### Task 2.3 — 生活方式图 `06-lifestyle-use.png`
- **优先级**: P1
- **依赖**: Task 1.1-1.3
- **方法**: image_generate
- **内容**: 杯子在桌面/咖啡场景中的使用。
- **验收**: 杯子设计清晰可见；场景温暖有质感。

---

## Phase 3: 包装与收藏（P1 — 商业落地关键）

### Task 3.1 — 包装设计展示 `07-packaging-application.png`
- **优先级**: P1
- **依赖**: Task 0.2（材料规格板）
- **方法**: image_generate
- **内容**: 特种纸包装盒+内衬完整设计。
- **验收**: 包装结构合理；rice-paper #f5f0e8 为主色；品牌名清晰。

### Task 3.2 — 收藏品展示 `08-collectible-detail.png`
- **优先级**: P1
- **依赖**: Task 1.1-1.3
- **方法**: image_generate
- **内容**: 5 个系列徽章完整收藏套装。
- **验收**: 5 个系列各有区分；排列有仪式感。

---

## Phase 4: 系列完整性（P2 — 补全五大系列）

### Task 4.1 — 材料变体 `09-alternative-material.png`
- **优先级**: P2
- **依赖**: Task 0.2
- **方法**: image_generate
- **内容**: 不同材质（木质/亚克力/金属）纪念品展示。
- **验收**: 材料质感差异清晰；设计语言一致。

### Task 4.2 — 五大系列总览 `10-series-overview.png`
- **优先级**: P2
- **依赖**: Task 1.1-1.3, Task 3.2
- **方法**: image_generate
- **内容**: 忠义/刚直/智谋/刚强/神话五主题视觉总结。
- **验收**: 5 个系列色彩区分明确（红/黑/白/蓝/金银）；每系列有代表性角色纹样。

---

## Phase 5: Gallery 页面（最后生成）

### Task 5.1 — 展示页面 `00-gallery.html`
- **优先级**: P2（最后）
- **依赖**: 所有 PNG 产物完成
- **方法**: manual（Designer 手写 HTML+CSS）
- **内容**: 整合所有设计产物的交互式画廊。包含 Design System、Design Specifications、Generated Artifacts 三个 section。
- **验收**: 所有 PNG 正确引用；使用 design_system.palette.tokens 色值；响应式布局。

---

## 设计系统选择说明

- **design_system_preference**: `let_system_choose` — 研究证据充分（8 种色彩象征、4 种行当、经典角色脸谱），从研究综合推导设计系统。
- **identity_essence**: 推断为 `innovation-momentum`（国潮=传统文化的创新 momentum）+ `warmth-community`（文创=与年轻人的温暖连接）。选择 `warm-humanistic` 作为 style_axis，因为文创产品需要人情味和可亲近感，而非冷冰冰的技术感。
- **voice_register**: 从 `innovation-momentum` 推导为 `confident-direct`（future-forward + confident + crisp），适配国潮的自信表达。
- **品牌命名**: 「脸谱潮 / LIANPU CHAO」—— 脸谱（产品核心）+ 潮（风格定位），直接、好记、有辨识度。

## 数量说明

- 用户未指定具体数量，按 full-set 模式执行。
- min_items = 3（规格板）+ 10（产品图）+ 1（gallery）= 14。
