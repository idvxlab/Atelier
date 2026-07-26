# 朱家角古镇游客中心空间设计 — 任务分解

## 设计系统说明

本项目为朱家角古镇游客中心空间概念设计，domain_type为`architecture_space_design`。设计系统从江南水乡「粉墙黛瓦、水木交融」的环境基因中提取，构建10个palette tokens、4个typography roles、4个motif母题、7种核心材料的完整体系。

## 交付物总量决策

用户要求「交付物详细丰富」，无具体数量限制。按architecture_space_design域的标准交付物类别，结合简报中明确命名的多个功能空间，决定产出**12张PNG + 1个HTML画廊 = 13个交付物**。

## 条件性输出选择

### 已选择的条件性输出

| 条件性输出 | 选择理由 |
|-----------|---------|
| site-context-relation (01) | 简报明确要求与古镇历史街区、水系协调共生 |
| spatial-sequence diagram (04) | 简报明确给出5段空间序列 |
| facade-elevation study (10) | 游客中心exterior identity对古镇入口区域至关重要 |
| accessibility-scale board (12) | 简报明确提到老年游客和无障碍需求 |
| multiple interior key moments (06-09) | 简报命名多个功能空间各有独立氛围需求 |

### 未选择的条件性输出

| 条件性输出 | 未选择理由 |
|-----------|-----------|
| day-night atmosphere pair | 光线策略已在material-light-board中集中表达 |
| detail vignette | 材料节点可在material-light-board中附带表达 |
| human-scale use scene (separate) | 所有效果图均包含人物活动，无需单独出图 |
| function annotation board | 功能分区已在02-master-plan-zoning中表达 |

## 任务优先级与执行顺序

### Phase 1: 基础分析图（P0 — 必须先完成，建立空间逻辑）

| 序号 | 交付物 | 方法 | 参考资产 | 要点 |
|-----|--------|------|---------|------|
| 01 | site-context-relation | image_generate | zhujiajiao-town-context | 鸟瞰轴测，展示游客中心与古镇环境关系 |
| 02 | master-plan-zoning | image_generate | — | 平面功能分区，8个核心区，模数化网格 |
| 03 | circulation-flow | image_generate | — | 4种流线，5段序列，颜色区分 |
| 04 | spatial-sequence | image_generate | — | 5个空间节点，收放节奏，轴测序列 |

### Phase 2: 空间研究图（P0 — 建立空间垂直关系与外观）

| 序号 | 交付物 | 方法 | 参考资产 | 要点 |
|-----|--------|------|---------|------|
| 05 | section-perspective | image_generate | anren-visitor-center-interior | 剖面透视，坡屋顶+天窗+木构梁架 |
| 10 | facade-elevation | image_generate | zhujiajiao-town-context, panlong-tiandi-precedent | 立面研究，新旧融合，人视视角 |

### Phase 3: 核心空间效果图（P0 — consistency anchor优先）

| 序号 | 交付物 | 方法 | 参考资产 | 要点 |
|-----|--------|------|---------|------|
| 06 | hero-entry-hall | image_generate | anren-visitor-center-interior, anren-visitor-center-precedent | **consistency anchor** — 木构梁架+天窗+粉墙黛瓦+水景 |
| 07 | reception-area | image_generate | anren-visitor-center-interior | 低位柜台+木构格栅+暖光 |
| 08 | cultural-exhibition | image_generate | anren-visitor-center-precedent | 木构格栅隔断+重点照明+水波纹理 |
| 09 | rest-area | image_generate | panlong-tiandi-precedent | 带扶手座椅+暖光+景观视线+老年游客 |

### Phase 4: 系统表达图（P1 — 集中表达材料与无障碍）

| 序号 | 交付物 | 方法 | 参考资产 | 要点 |
|-----|--------|------|---------|------|
| 11 | material-light-board | image_generate | anren-visitor-center-interior | 7种材料样本+光线策略 |
| 12 | accessibility-scale | image_generate | — | 无障碍坡道+低位柜台+通道宽度+人物尺度 |

### Phase 5: 画廊整合（P0 — 最终交付）

| 序号 | 交付物 | 方法 | 要点 |
|-----|--------|------|------|
| 00 | gallery | manual | 嵌入12张PNG，按category分组，顶部palette+type stack |

## 关键设计决策记录

### 1. 色彩体系选择

从朱家角古镇「粉墙黛瓦、水木交融」的环境色谱中提取10个tokens：
- **whitewash(#F2EDE4)** — 粉墙白，主墙面基调
- **tile-grey(#4A4A48)** — 黛瓦灰，结构框架
- **timber-warm(#8B6B4A)** — 木色棕，温度来源
- **water-cyan(#7BA3A0)** — 水色青，点缀
- **stone-slab(#9C978E)** — 石板灰，地面
- **warm-amber(#D4A853)** — 暖光黄，照明色温
- **ink-dark(#2C2C2A)** — 墨色深灰，文字对比
- **brick-terracotta(#A67B5B)** — 砖色赭，材料层次
- **mist-green(#B8C9B8)** — 烟绿，植物景观
- **concrete-light(#D5D0C8)** — 清水混凝土色，现代材料

### 2. 空间语汇当代转译策略

不直接复制传统建筑构件，而是抽象转译：
- **坡屋顶轮廓** → 天花造型、标识底形
- **水波纹理** → 地面铺装、金属屏风、灯光投影
- **木构格栅** → 空间隔断、立面遮阳
- **月洞门/圆窗** → 空间过渡、取景框

### 3. 先例参考策略

- **安仁游客中心（李兴钢）**：参考其新旧融合策略、木构表达、空间层次，但不复制具体形态
- **蟠龙天地（BWSS/Sasaki）**：参考其沿河布局、传统现代融合、商业文化复合
- **现有朱家角游客中心（无样建筑工作室）**：了解现状，但明确不复制其建筑形态

### 4. 无障碍设计策略

无障碍设计是底线而非加分项：
- 主要出入口无高差或设缓坡（坡度≤1:12）
- 主要通道宽度≥1.8m
- 服务台设低位柜台（高度≤750mm）
- 标识系统配合盲文、大字、高对比度
- 休憩区设带扶手座椅

## 开放问题（需用户确认）

1. 游客中心的具体选址位置尚未明确
2. 与现有游客服务中心的功能互补或替代关系未定
3. 文化展览的具体主题和内容方向未定
4. 大客流承载能力的具体指标未定
5. 是否需要设置餐饮、零售等商业配套功能

## 执行注意事项

1. **所有效果图必须引用design_system.palette中的具体token名称或hex值**
2. **材料描述必须引用material_atmosphere中的具体材料名称**
3. **空间构图必须体现motif_system中的至少一个母题**
4. **每张效果图应包含适度人物活动，体现空间真实使用状态**
5. **色彩基调严格遵循whitewash+tile-grey+timber-warm三色体系**
6. **禁止出现高饱和度荧光色、冷蓝科技色、纯白#FFFFFF或纯黑#000000大面积使用**
7. **禁止直接复制传统建筑构件或使用具象龙凤、祥云纹样**
8. **禁止复制现有游客中心或官方标志**
