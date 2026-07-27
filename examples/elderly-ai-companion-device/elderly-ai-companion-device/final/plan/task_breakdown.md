# 任务分解 — 老年 AI 陪伴设备

> 按优先级排序。Designer 应按此顺序执行。

---

## 阶段 0：设计规范板（优先生产，为后续渲染定调）

| 优先级 | 任务 ID | 交付物 | 说明 |
|--------|---------|--------|------|
| P0 | color_palette | `artifacts/design-spec/color-palette.png` | 色板规范：展示 design_system.palette 全部 8 个 token 的色块、hex 值、角色标注、对比度数据。背景 surface-cream，文字 text-charcoal。 |
| P0 | material_board | `artifacts/design-spec/material-board.png` | 材质规范：4-6 种材质样本（织物编织、浅橡木纹、哑光软触塑料、LED 扩散体、织物×塑料交接）。暖光照明，Kinfolk 风格平铺。 |
| P0 | visual_language | `artifacts/design-spec/visual-language.png` | 视觉语言板：展示 breathing-arc 母题三元素（breath-ring 同心弧、pebble-curve 有机曲线、warm-glow 径向渐变），以及它们在产品/版面中的应用示意。 |
| P0 | form_language | `artifacts/design-spec/form-language.png` | 形态语言板：鹅卵石隐喻的形态演化——从自然鹅卵石 → 几何抽象 → 产品轮廓。展示比例关系（高宽比 1.3-1.5:1）、G2 连续曲线、最小圆角 8mm 标注。 |

## 阶段 1：核心产品定义

| 优先级 | 任务 ID | 交付物 | 说明 |
|--------|---------|--------|------|
| P1 | 01-form-study | `artifacts/generated-images/01-form-study.png` | 形态研究：3-4 个有机形态方案的侧影/正视图。方案 A：鹅卵石型（不对称圆润）；方案 B：水滴型（上窄下宽）；方案 C：圆柱+圆顶型（稳定感）。所有方案共享 surface-cream 主体 + accent-wood 底座。 |
| P1 | 02-form-variant | `artifacts/generated-images/02-form-variant.png` | 选定方案的多角度展示（正面/侧面/45°俯视/背面）。展示 glow-amber LED 环在上部 1/3 处的位置。表面无可见螺丝/缝隙。 |
| P1 | 05-material-board | `artifacts/generated-images/05-material-board.png` | CMF 方案板（产品级）：展示选定设计的材质应用——织物包裹区域、木质底座、按钮材质、LED 透光区域。与 design-spec/material-board 呼应但更聚焦产品。 |

## 阶段 2：功能与工程

| 优先级 | 任务 ID | 交付物 | 说明 |
|--------|---------|--------|------|
| P2 | 03-mechanism-overview | `artifacts/generated-images/03-mechanism-overview.png` | 功能机制概览：标注扬声器（织物后）、麦克风阵列（顶部）、LED 光环（上部 1/3）、触控按钮（正面）、充电触点（底部）。使用 text-charcoal 标注线。 |
| P2 | 04-ergonomic-diagram | `artifacts/generated-images/04-ergonomic-diagram.png` | 人机工程分析：老年手部（简化、温暖肤色）触摸设备正面按钮的场景。标注按钮直径 ≥25mm、设备高度（坐姿桌面）、视角舒适度。 |
| P2 | 10-exploded-view | `artifacts/generated-images/10-exploded-view.png` | 爆炸视图：5+ 层结构——织物外壳 → LED 导光环 → 扬声器模组 → 主板+电池 → 木质底座。各层材质可辨识，爆炸间距均匀。 |

## 阶段 3：细节与语境

| 优先级 | 任务 ID | 交付物 | 说明 |
|--------|---------|--------|------|
| P3 | 06-production-context | `artifacts/generated-images/06-production-context.png` | 生产/工艺语境：展示模块化结构——织物套可拆卸清洗、木底座可分离、装配关系。体现可维护性设计。 |
| P3 | 07-detail-connection | `artifacts/generated-images/07-detail-connection.png` | 细节微距：≥3 个特写——按钮表面纹理（同心圆防滑纹）、LED 光扩散效果（warm-glow 渐变）、织物与塑料交接（无缝过渡）。2700K 暖光。 |
| P3 | 08-scale-reference | `artifacts/generated-images/08-scale-reference.png` | 尺度参考：产品与茶杯、手掌、小书并置。传达 120-150mm 直径、<1kg 重量感。温暖家居背景。 |
| P3 | 09-lifestyle-context | `artifacts/generated-images/09-lifestyle-context.png` | 生活场景：设备在客厅边桌上，旁边有茶杯和书，2700K 暖光环境。老人手部入画（不露脸），轻触设备顶部。Kinfolk 杂志美学。 |

## 阶段 4：画廊整合

| 优先级 | 任务 ID | 交付物 | 说明 |
|--------|---------|--------|------|
| P4 | 00-gallery | `artifacts/00-gallery.html` | 画廊页面：包含 (1) Design System 概览——标题、设计意图、色板色块；(2) Design Specifications——4 张规范板；(3) Generated Artifacts——10 张效果图，按阶段分组。响应式 CSS Grid 布局，暖色调主题（surface-cream 背景、text-charcoal 文字）。无外部依赖。 |

---

## 设计系统选择说明

- **design_system_preference**：brief 中未指定（`let_system_choose`），因此从研究证据综合推导。选择 warm-humanistic 风格轴，因为研究一致指向"温暖 + 家居融合 + 非医疗"方向。
- **identity_essence**：本项目为 speculative_concept（无现有品牌），从研究中推导出 `warmth-community` 原型——核心情感是"陪伴感 + 安全感 + 自然感"。
- **voice register**：由 warmth-community 原型推导为 `warm-conversational`（humanistic + warm + accessible）。
- **style axis**：由 (warmth-community, warm-conversational) 推导为 `warm-humanistic`，第二选择 `craft-minimal`。
- **产品命名**：使用"伴 (Bàn)"作为概念占位名——取"陪伴"之意，字形含"人"旁，暗示人的在场。

## 关键约束提醒

1. 不得复制竞品标志性特征（brand_lock.md do_not_duplicate 清单）
2. 所有曲线 G2 连续，最小圆角 8mm
3. 色彩仅使用 design_system.palette.tokens 中的 8 个色值
4. 不得出现纯黑/纯白/冷灰/高饱和色
5. 不得出现医疗/临床/监控/玩具美学
6. 老人形象仅展示手部，不展示面部（隐私/尊严）
7. 所有渲染使用 2700K-3000K 暖光照明
