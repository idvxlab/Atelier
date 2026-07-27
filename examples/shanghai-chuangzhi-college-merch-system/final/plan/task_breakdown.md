# Task Breakdown — 上海创智学院产品周边系统

1. **P1 / 锁定系统合同**
   - 以 `plan/design_system.json` 为唯一上游合同。
   - 全部后续 prompt 必须逐字引用颜色 hex：`#0F5BFF`、`#0B1220`、`#F7F9FC`，并按需补充 `#5ED3FF`、`#A8B3C7`。
   - 明确使用 typography roles：`display`、`headline`、`subhead`、`body`、`caption`、`mono`。

2. **P1 / 正视研究限制并约束身份表达**
   - 本轮 research 已证明官方身份存在，但 `research/assets/validation.json` 为 `ready:false`，原因是缺少可工具验证的独立 protected/logo 资产文件。
   - 因此设计必须避免虚构 logo，不创建任何新校徽、缩写主标或 emblem。
   - 品牌识别优先使用正式校名写法、官网蓝白语境、纪实场景图像与信息层图形。
   - 由于 asset validation 未 ready，维持较稳健的 10 PNG + 1 gallery 计划，不追加更多依赖强资产的 deliverables。

3. **P1 / 先做三张系统锚点图**
   - 完成 `01-logo-application-poster`、`02-campaign-poster-zh`、`03-campaign-poster-en`。
   - 目标：在没有独立 logo 文件的前提下，用正式校名锁定身份，并建立科技未来但克制的总基调。

4. **P1 / 产出产品周边主展示图**
   - 完成 `04-social-card-announce`、`07-merch-mockup`、`09-moodboard`。
   - 确保至少三类通用周边在系统中被清晰展示，适合“通用混合套装”定位。

5. **P2 / 产出基于官方资产的真实场景延展**
   - 使用 `image_edit` 完成 `05-social-card-portrait`、`08-signage-mockup`、`10-application-on-campus`。
   - 只使用官方学院资产；不得把 peer 资产带入最终图。
   - 对原图进行裁切、覆盖、mockup 化处理，避免原样复用。

6. **P2 / 完成纯文字召唤卡与最终展示页**
   - 完成 `06-social-card-call`，测试 type-only 情况下系统是否依然成立。
   - 编写 `artifacts/00-gallery.html`，置顶展示 palette swatches、typography roles、motif 名称，并汇总所有 PNG。

7. **P3 / 最终自检**
   - 对照 `plan/acceptance_criteria.md` 与 `plan/deliverable_manifest.json` 逐项核验。
   - 确认没有伪 logo、没有第三方 logo、没有 AI 科技俗套图案、没有路径缺失。