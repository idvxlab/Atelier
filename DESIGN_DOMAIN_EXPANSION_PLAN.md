# Atelier 设计门类扩展计划

## 1. 产品定位

Atelier 近期不需要变成完整的 CAD、BIM、工程制图、制造或施工系统，但是曹老师要求他能支持别的设计门类，不能只是品牌设计。我们现阶段的产品定位可以更清楚地写成：

> 用户给出一个设计任务后，Atelier 负责查找参考资料、形成设计方向，并输出一组 PNG 效果图和一个整理好的展示页面，以及一些设计规范比如色卡之类的（目前缺少）。

所以，其他设计门类的支持，第一阶段不需要追求专业软件级别的完整交付，而是先支持“视觉概念效果图”的生成。比如：

- 产品设计：产品概念图、使用场景图、CMF 材料色彩板、包装或发布视觉。
- 品牌形象设计：标志应用、海报、社交媒体图、周边、导视、视觉系统展示。
- 建筑设计：建筑外观概念图、室内氛围图、立面风格探索、场地氛围板。
- 工业产品设计：形态探索、材料与配色变体、使用场景、产品族概念板。
- 广告海报设计：主视觉海报、系列海报、社媒延展、campaign key visual。
- 文创周边设计：周边产品效果图、纹样系统、包装、陈列展示页。

共享的输出形态仍然可以保持不变：

- `research/`：资料、证据、参考图片库。
- `plan/`：设计系统、交付清单、验收标准。
- `artifacts/`：生成或编辑得到的 PNG 图片。
- `artifacts/00-gallery.html`：整理好的展示页面。
- `review/`：critic 的评价报告。
- `final/`：最终导出的结果包。

## 2. 当前工作流现状

现在的简化工作流是：

`design-primary -> design-research -> design-planner -> design-designer -> design-critic -> export_package`

这个链路本身是有通用价值的：

- Research 负责找资料、找参考图、记录证据。
- Planner 负责形成设计系统和交付清单。
- Designer 负责生成 PNG 图片和展示页。
- Critic 负责检查完整性、资料 grounding、一致性和成品质量。

但是，现在的 prompt 和 skill 仍然明显偏向品牌视觉和平面传播设计。默认交付物包括：

- logo application poster
- campaign poster
- social card
- merch mockup
- signage mockup
- moodboard
- application on campus
- gallery HTML

这对品牌形象设计、广告海报、招生宣传、实验室视觉、文创周边很合适，但对于产品设计、建筑设计、工业设计、空间设计来说还不够通用。

所以我们接下来不是推翻现有工作流，而是在现有工作流上做“门类扩展”。

## 3. 当前 contract 审计结果

这一节记录当前 prompt / skill / tool contract 的状态，后面改做法二时反复参考。

### 3.1 总体链路

当前固定链路是：

`design-primary -> design-research -> design-planner -> design-designer -> design-critic -> export_package`

| 阶段 | 当前职责 | 核心输出 |
| --- | --- | --- |
| Primary | 解析 brief、澄清需求、初始化 run、调度子智能体 | `brief.json`、bus kickoff、最终汇报 |
| Research | 查资料、找参考图、记录已有品牌/身份资产 | `evidence.json`、`research.md`、`brand_lock.md`、`assets/manifest.json` |
| Planner | 写设计系统、设计计划、交付清单、验收标准 | `design_system.json`、`design_plan.json`、`deliverable_manifest.json`、`acceptance_criteria.md`、`task_breakdown.md` |
| Designer | 根据计划生成/编辑 PNG，写 gallery | PNGs、`00-gallery.html`、`artifact-manifest.json` |
| Critic | 检查成果完整性、grounding、一致性、质量 | `critique.md`、`critique.json`、`evaluator_pass/fail` |

### 3.2 当前 `resolvedScope` 的核心

现在 `resolvedScope` 主要围绕品牌识别框架：

| 字段 | 意义 | 当前偏向 |
| --- | --- | --- |
| `mind_identity` | 理念识别：是谁、价值、信任点、想唤起什么感觉 | 品牌/机构定位 |
| `behavior_identity` | 行为识别：语气、受众、行为信号 | 品牌传播语气 |
| `visual_identity` | 视觉识别：设计系统偏好、风格轴、审美约束 | VI / 视觉系统 |

这套 MI / BI / VI 很适合品牌形象设计，但如果做建筑、产品、工业设计，会显得不够直接。做法二要新增的是“门类上下文”，但不应该把所有系统推理都塞进 `resolvedScope`。

建议：

- `resolvedScope` 存用户需求澄清结果。
- `domain_type` 可以作为轻量字段进入 `resolvedScope`，因为它是用户任务类型的一部分。
- `professional_factors`、`reference_strategy`、`deliverable_categories`、`evaluation_focus` 更适合进入 `domain_context`、bus message 和 plan 文件。

### 3.3 当前 bus 传递内容

当前 bus 比较轻，主要传阶段状态和文件引用：

| 消息类型 | 谁发 | 主要内容 |
| --- | --- | --- |
| `kickoff` | Primary -> Research | runId、runDir、brief、scope |
| `research_done` | Research -> Primary | research 文件路径、资产验证摘要 |
| `plan_done` | Planner -> Primary | plan 文件路径、设计系统摘要 |
| `design_done` | Designer -> Primary | artifact 路径、lint 摘要 |
| `evaluator_pass/fail` | Critic -> Primary | verdict、修复建议 |
| `plan_amendment` | Planner -> all | 局部计划修正 |

目前 bus 没有正式传递“设计门类”和“门类专业要素”。这是做法二最适合补的位置。

### 3.4 当前最强能力

现在最成熟的是：

- 品牌形象设计。
- 广告海报。
- 视觉系统。
- 周边 mockup。
- 社交媒体图。
- 导视 / 应用场景图。
- moodboard。
- 参考图 grounding。
- PNG + gallery 输出。

因为 Planner 默认交付物就是这些：

- logo application poster
- campaign poster zh/en
- social card
- merch mockup
- signage mockup
- moodboard
- application on campus
- gallery HTML

### 3.5 当前主要偏置来源

| 文件 | 偏置点 |
| --- | --- |
| `design-research.md` | 搜索矩阵强制找 logo、VI、品牌手册、官网、校园图 |
| `brand-identity/SKILL.md` | 整套理论是品牌定位、MI/BI/VI、logo、palette、lockup |
| `design-system/SKILL.md` | schema 以 palette、typography、grid、motif、voice、lockup 为中心 |
| `design-planner.md` | 默认 deliverable table 是海报、社媒、周边、导视 |
| `image-prompting/SKILL.md` | 示例和规则大量围绕 logo、poster、brand work |
| `visual-composition/SKILL.md` | poster / social grid 很明确 |
| `critic-rubric/SKILL.md` | system consistency、non-duplication、lockup drift 等偏品牌系统 |

### 3.6 当前 contract 不一致点

有一个历史残留需要后续顺手修：

- `design-planner.md` 说输出 `plan/design_plan.json`。
- `design-harness-protocol/SKILL.md` 的目录结构仍写 `plan/design_direction.md`。
- `design-designer.md` 输入里也写了读取 `<runDir>/plan/design_direction.md`。

这可能会导致 Designer 找旧文件。做法二修改时建议统一成 `design_plan.json`。

### 3.7 工具层也需要一起关注

做法二不是只改 prompt 和 skill，也要看内置工具是否把当前品牌视觉假设写死了。至少需要关注：

- `harness/tools/builtin/design_research.py`
  - 是否默认围绕 logo / brand / campus / official site 做资产分类。
  - `research_asset_discover` 和 `research_asset_fetch` 的 `kind` 是否需要扩展，比如 `product`, `material`, `interior`, `facade`, `site`, `packaging`, `pattern`, `scenario`。
  - `research_asset_validate` 的健康标准是否过度依赖 logo / protected assets。
- `harness/tools/builtin/design_image.py`
  - `image_generate` / `image_edit` 的参数是否足够表达不同门类的效果图。
  - `size` 和输出目录是否适合产品、建筑、空间等不同画幅。
  - sidecar 是否需要记录 `domain_type`、`professional_factor`、`deliverable_category`，方便 Critic 后续检查。
- `harness/tools/builtin/design_run.py`
  - `run_init` 写入的 `brief.json` 是否适合保存 `domain_context`。
  - final/export 结构是否需要包含门类摘要。
- `artifact_lint`
  - 当前 lint 可能偏向 `design_system` / palette / lockup / token citation。
  - 做法二可能需要让 lint 同时检查 `domain_context`、PNG 数量、gallery、sidecar 中的门类字段。

工具层原则：

- prompt 负责告诉 agent 怎么思考。
- skill 负责定义工作流和专业 contract。
- tool 负责把 contract 变成可验证的数据结构。

如果只改 prompt，不改工具和 lint，系统可能能“说”自己支持产品/建筑，但很难稳定检查它是否真的支持。

## 4. 三种扩展做法

### 做法一：把现有 prompt 和 skill 写得更宽泛



目标：

让现有工作流不要被“品牌、logo、海报、社交媒体图”这些词锁死，而是能自然接住更多设计任务。

主要改动：

- 把过于具体的词改宽，比如：
  - `brand assets` 改成 `design assets`
  - `logo application` 改成 `application scene`
  - `campaign poster` 改成 `presentation visual` 或 `key visual`
  - `social card` 改成 `supporting visual`
- 保持“一组 PNG + 一个 gallery HTML”的输出形态。
- 让 Planner 根据 brief 选择交付物，而不是总是套用品牌视觉表格。
- 保留现在的 `image_generate`、`image_edit`、`artifact_lint`、`critic` 结构。

优点：

- 实现最快。
- 对现有品牌/海报工作流影响最小。
- 可以让产品、建筑、工业设计类 prompt 不再显得别扭。


### 做法二：让 bus 和交接内容支持不同设计门类


目标：

让不同智能体之间传递的信息能体现“这是哪一类设计任务”，并且把该门类需要关注的专业要素传下去。

主要改动：

这里需要区分两个东西：

- `resolvedScope`：更适合存“用户需求被澄清后的结果”。它回答的是：用户到底要什么、面向谁、有什么偏好和限制。
- `domain_context` / bus / plan 文件：更适合存“系统根据门类推导出的工作上下文”。它回答的是：这个门类应该关注什么、查什么、产出什么、怎么评价。

所以，`domain_type` 可以作为轻量分类结果写入 `resolvedScope` 或 `brief.json`，因为它是对用户任务类型的基本识别。但 `professional_factors`、`reference_strategy`、`deliverable_categories`、`evaluation_focus` 不应该直接塞进 `resolvedScope`，否则会把“用户需求”和“系统推理”混在一起。

更推荐的结构是：

```json
{
  "resolvedScope": {
    "target": "用户要设计的对象",
    "audience": "目标受众",
    "language": "输出语言",
    "deliverable_intent": "用户明确提出的交付意图",
    "style_preferences": "用户明确表达的风格偏好",
    "constraints": "用户明确提出的限制",
    "domain_type": "product_design | brand_identity | architecture_design | ..."
  },
  "domain_context": {
    "output_goal": "curated PNG concept set plus gallery",
    "professional_factors": [],
    "reference_strategy": [],
    "deliverable_categories": [],
    "evaluation_focus": []
  }
}
```

其中 `resolvedScope` 由 Primary 通过解析 brief 和必要澄清得到；`domain_context` 可以由 Primary 初步推断，再由 Research / Planner 在 bus 和 plan 文件中不断具体化。

门类上下文字段包括：

- `domain_type`：设计门类。
- `output_goal`：本次要输出什么类型的效果图。
- `professional_factors`：这个门类需要关注的专业要素。
- `reference_strategy`：应该找什么类型的参考图。
- `deliverable_categories`：应该生成哪些类型的 PNG。
- `evaluation_focus`：critic 应该重点看什么。

可以先支持这些门类：

- `brand_identity`
- `advertising_poster`
- `product_design`
- `industrial_design`
- `architecture_design`
- `spatial_design`
- `packaging_design`

不同门类的专业要素示例：

- 产品设计：用户场景、功能层级、形态语言、CMF、尺度感、人机关系。
- 工业产品设计：材料逻辑、制造暗示、结构合理性、耐用性、产品族一致性。
- 建筑设计：场地关系、体量、立面节奏、光线、动线、人尺度、周边环境。
- 空间设计：氛围、动线、功能分区、材质、灯光、家具尺度。
- 广告海报：传播信息、视觉记忆点、图文关系、受众识别、渠道适配。
- 品牌形象：识别度、一致性、非重复、延展触点、系统完整性。

这样每个阶段就可以按门类适配：

- Research 按门类找不同参考。
- Planner 按门类写不同 manifest。
- Designer 按门类生成不同类型 PNG。
- Critic 按门类检查不同标准。

优点：

- 比单纯改宽 prompt 更可靠。
- 每次运行的门类判断和专业要素会写进文件，方便检查和 debug。
- 仍然保持现有 agent 链路不变。

局限：

- 需要改多个 persona 和 skill。
- 如果门类表设计得太死，可能会限制模型处理混合型设计任务。

### 做法三：加入通用设计推理引导



目标：

不是把每个门类的规则都硬编码进去，而是让智能体先判断设计门类，再自己推理该门类应该关注哪些专业要素。

主要改动：

给 Planner / Designer / Critic 加一层通用推理要求：

1. 先判断这个 brief 属于什么设计门类。
2. 再推理这个门类的专业成功标准是什么。
3. 再判断这些标准里哪些可以通过 PNG 效果图表达出来。
4. 再决定 research 应该找什么参考，planner 应该生成什么 deliverables。
5. Designer 每张图都要回答一个明确的设计问题。
6. Critic 不只看“好不好看”，还要看是否回答了这个门类的设计问题。

现在的品牌/海报工作流可以作为一个例子，但不应该作为唯一模板。

可以新增一个 skill，例如：

- `design-domain-reasoning`

它可以要求模型使用这样的推理框架：

- 这个任务主要是哪类设计？
- 这个门类中专业设计师通常关心什么？
- 哪些因素适合用效果图表达？
- 本次应该输出哪几类 PNG？
- 每张 PNG 分别验证哪个设计判断？
- Critic 应该如何评价这些判断？

优点：

- 泛化能力最好。
- 可以处理没有提前写入 taxonomy 的新门类。
- 更符合“设计智能体”而不是“模板生成器”的定位。

局限：

- 更依赖模型能力。
- 结果可能不稳定，需要约束字段在传递过程中的稳定，建议把一些推导出的关键要素的写在bus里，让他知道有哪些新的字段。

## 5. 成功标准

扩展成功的判断标准不是“能不能输出所有专业文件”，而是：

- 每个门类都能稳定输出真实 PNG 成果。
- gallery 能清楚整理最终结果，而不是堆文件。
- Research 找到的参考和门类相关。
- Planner 能说明该门类的专业要素。
- Designer 的图片 prompt 能体现这些专业要素。
- Critic 不只看视觉美观，也检查是否回答了设计问题。
