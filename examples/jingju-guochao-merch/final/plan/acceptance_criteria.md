# 验收标准 — 京剧脸谱国潮文创系列

> 本文件定义所有交付物的验收条件。Critic 将逐条对照评分。
> 所有涉及 palette / type / motif / voice / lockup 的条目均引用 `design_system.json` 中的 token 名称。

---

## 1. 设计系统一致性（System Consistency）

- [ ] **色板锁定**：所有 PNG 产物中出现的颜色必须来自 `design_system.palette.tokens` 的 7 个色值（cinnabar-red #e8433f / gold-leaf #d4a843 / ink-black #1a1a2e / rice-paper #f5f0e8 / azurite-blue #2d6a8e / gamboge-yellow #f0b32d / jade-green #3a8c6e）。不得出现色板外的颜色（尤其是纯黑 #000000、纯白 #ffffff、额外红色）。
- [ ] **字体角色**：所有文字使用 `design_system.typography.roles` 中定义的角色——display（Source Han Sans CN Heavy / Montserrat Black）用于系列标题，headline（Bold）用于角色名称，body（Regular）用于文化叙述。不得出现未定义的字体风格。
- [ ] **纹样系统**：所有辅助图形必须来自 `design_system.motif_system.name`「脸谱解构纹样 / Deconstructed Lianpu Patterns」——额头图案解构、眼窝造型、脸谱轮廓线、装饰纹样、色块分割。不得出现与脸谱无关的装饰元素。
- [ ] **品牌名**：所有产物中品牌名必须为「脸谱潮 / LIANPU CHAO」，中文在上、英文在下，英文字号为中文的 60%。不得出现其他品牌名。
- [ ] **撞色策略**：核心撞色对为红+金、蓝+黄、黑+白。每张图片至少使用一组撞色对，体现潮酷风的大胆色彩对比。

---

## 2. 文化真实性（Cultural Authenticity）

- [ ] **色彩象征准确**：脸谱色彩必须对应研究证实的象征含义——红=忠义（关羽）、黑=刚直（包拯）、白=智谋（曹操）、蓝=刚强（窦尔敦）、金银=神仙（孙悟空）。不得出现色彩与角色错配。
- [ ] **脸谱对称性**：所有脸谱图案必须保持对称结构——这是京剧脸谱的核心文化特征。不对称设计视为文化错误。
- [ ] **角色可辨识**：每个系列的代表角色（关羽/包拯/曹操/窦尔敦/孙悟空）的脸谱特征必须可辨识——关羽的凤眼、包拯的月牙、曹操的白脸、窦尔敦的蓝脸、孙悟空的金银脸。
- [ ] **纹样来源**：所有纹样元素必须可追溯到京剧脸谱的真实图案——额头纹、眼窝、鼻窝、嘴部图案。不得凭空发明与脸谱无关的图案。
- [ ] **无文化混搭**：不得将京剧脸谱元素与日式、韩式或其他文化符号混搭。这是中国传统文化的独立表达。

---

## 3. 视觉质量（Visual Quality）

- [ ] **潮酷风美学**：所有产物必须体现国潮潮酷风——大胆撞色、粗轮廓线（3-6px at 1024px）、强对比、街头涂鸦能量。不得出现细线条、写实风格、过度光滑的商业摄影感。
- [ ] **无 AI 陈词滥调**：不得出现以下 AI 设计 clichés：random radial gradients、AI glowing nodes、neural net node clusters、hexagonal honeycombs、brain silhouettes、circuit board patterns、holographic iridescent foil、generic dragon motifs、random Chinese calligraphy decoration、fake Latin text、emoji as design elements。
- [ ] **产品质感可感知**：珐琅徽章必须体现金属边框+色块填充的珐琅质感；陶瓷杯必须体现釉面光泽；特种纸包装必须体现纸张纹理。
- [ ] **构图有节奏**：产品排列不得简单平铺——需有主次、疏密、节奏感。参考 design_system.grid 的网格系统。
- [ ] **文字清晰可读**：所有 on-image 文字必须清晰可读，不得被背景图案干扰。使用 ink-black on rice-paper 或 rice-paper on ink-black 确保对比度。

---

## 4. 交付物完整性（Deliverable Completeness）

- [ ] **3 张设计规格板**：cultural-palette.png（色彩象征体系）、material-board.png（材料工艺）、iconography.png（纹样系统）必须全部生成。
- [ ] **10 张产品图**：01-product-overview 到 10-series-overview 全部生成，每张对应 deliverable_manifest.json 中定义的 purpose。
- [ ] **1 个展示页面**：00-gallery.html 包含 Design System、Design Specifications、Generated Artifacts 三个 section，所有 PNG 正确引用。
- [ ] **总计 14 件产物**：min_items = 3（规格板）+ 10（产品图）+ 1（gallery）= 14。

---

## 5. 品牌语言（Voice & Tone）

- [ ] **品牌调性**：所有文案必须体现「confident-direct」register——自信、直接、有文化底气但不说教。
- [ ] **关键词覆盖**：至少使用以下 principle_keywords 中的 5 个：忠义、刚直、智谋、刚强、神话、潮酷、撞色、国潮、文化自信、个性表达。
- [ ] **禁止说教**：不得出现「传承中华文化」「非物质文化遗产」「国粹精华」「弘扬传统艺术」「中国风设计」等官方/学术/老派表述。
- [ ] **Z 世代语境**：文案应像「一个懂传统文化又懂街头潮流的朋友在分享好东西」，而非官方宣传稿。

---

## 6. 产品系列验收（Per-Series Acceptance）

### 忠义红系列（关羽）
- [ ] 以 cinnabar-red #e8433f 为主色，占视觉面积 30-40%
- [ ] 关羽红脸纹样清晰可辨（凤眼、红面、长髯暗示）
- [ ] gold-leaf #d4a843 作为点缀色体现品质感

### 刚直黑系列（包拯）
- [ ] 以 ink-black #1a1a2e 为主色
- [ ] 包拯月牙纹样作为核心图案
- [ ] 金色点缀体现「铁面无私」的庄重感

### 智谋白系列（曹操）
- [ ] 以 rice-paper #f5f0e8 为主色（白脸）
- [ ] 曹操白脸特征可辨（细眼、白面、奸诈感）
- [ ] 使用 azurite-blue 或 gamboge-yellow 作为点缀增加层次

### 刚强蓝系列（窦尔敦）
- [ ] 以 azurite-blue #2d6a8e 为主色
- [ ] 窦尔敦蓝脸特征可辨
- [ ] 体现「刚强桀骜」的性格特征

### 神话金银系列（孙悟空）
- [ ] 以 gold-leaf #d4a843 为主色
- [ ] 孙悟空金银脸特征可辨（猴脸、火眼金睛暗示）
- [ ] 体现「超凡神仙」的神话感

---

## 7. Gallery 页面验收

- [ ] 页面标题包含「脸谱潮 / LIANPU CHAO」
- [ ] Design System section 展示 7 个 palette token 的色块和色值
- [ ] Design Specifications section 展示 3 张规格板
- [ ] Generated Artifacts section 展示 10 张产品图，每张有标题和简述
- [ ] 页面使用 design_system.palette.tokens 中的色值作为 UI 颜色
- [ ] 响应式布局，在 1024px+ 宽度下正常显示
