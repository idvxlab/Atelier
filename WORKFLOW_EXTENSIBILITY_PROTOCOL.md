# Dreamatic 可扩展工作流协议

> 状态：实现依据。
>
> 目标：所有 Skill 都以自然语言描述按需发现和加载。当前稳定设计流程作为默认 Skill；用户可以安装并指定新的专业 Skill 或工作流 Skill。

## 1. 基本原则

Dreamatic 不对 Skill 做强制分类，也不要求 Skill 声明固定类型。

每个 Skill 只需要：

```yaml
---
name: skill-name
description: 清楚说明这个 Skill 适合什么任务，以及会改变智能体的哪些工作方式。
---
```

Skill 可以同时包含专业知识、工作方法、评价标准和完整工作流。系统不要求作者把它归入 `workflow`、`domain`、`capability`、`protocol` 或 `rubric`。

已有 `metadata` 可以继续保留，也允许作者写任意新字段；Dreamatic 核心不根据这些字段限制 Skill 的加载和使用。

## 2. Skill 如何被发现和使用

系统在会话启动时向模型提供所有可用 Skill 的：

- `name`
- `description`
- `source`

模型根据用户要求和当前任务判断是否需要加载完整内容。只有调用 `use_skill` 后，Skill 正文才进入当前上下文。

选择顺序：

1. 用户明确指定某个 Skill 时优先加载。
2. 当前任务与某个 Skill 的 description 清晰匹配时，可以按需加载。
3. 工作流正文明确要求加载其他 Skill 时，相关子智能体按要求加载。
4. 没有匹配 Skill 时，智能体继续使用基础 persona 和已有工具完成任务。

无分类 Skill、带自定义 metadata 的 Skill 和来自用户全局目录的 Skill 都遵循同样规则。

## 3. 专用智能体的形成方式

一个运行中的专用智能体由以下内容组合而成：

```text
专用智能体
  = 基础 Persona
  + 当前阶段任务
  + 已加载 Workflow Skill
  + 已加载专业/方法 Skills
  + 当前项目上下文
```

例如：

```text
design-research
  + exhibition-design
  + museum-visitor-research
  = 本轮的博物馆展陈研究智能体
```

Skill 可以改变智能体的专业知识、检查重点和执行方法，但不能扩大 persona 的工具权限。Persona 仍然决定：

- `allowed_tools`
- 审批模式
- 是否可以派生子智能体
- 可访问的运行时能力

## 4. 普通 Skill 与工作流 Skill

核心系统不需要预先判断 Skill 属于哪一类。

当出现以下任一信号时，Primary 可以把一个 Skill 作为本次工作流：

1. 用户明确说“使用 `<skill-name>` 作为工作流”。
2. `/design` 或未来前端入口明确提供 `requested_workflow`。
3. Skill description 明确表示它会编排多个阶段或子智能体，并且用户要求采用它。

如果用户只说“使用 `<skill-name>`”，但它更像专业知识或方法，Primary 将它作为补充 Skill 加载，并继续使用默认工作流。

Primary 不应仅因为安装了一个新 Skill 就自动改变已有任务的工作流。第三方工作流需要用户明确指定，避免新增 Skill 后改变默认行为。

## 5. 工作流 Skill 的正文约定

工作流 Skill 不要求机器可解析的 YAML stages。为了让 Primary 稳定执行，正文应尽量说明：

- 工作流目标
- 阶段及顺序
- 每个阶段使用的基础 persona
- 每个阶段应加载的 Skill
- 阶段输入
- 阶段交付
- 阶段完成条件
- 失败、重试和修复方式
- 最终交付与汇报方式

推荐写法：

```markdown
# Exhibition Design Workflow

## Goal

完成展览叙事、空间规划、视觉呈现和评审。

## Stages

### 1. Research

- Agent: design-research
- Load: exhibition-design, visitor-research
- Inputs: user brief and references
- Deliver: cited research and visitor findings
- Complete when: the requested research files exist and the agent reports completion

### 2. Planning

- Agent: design-planner
- Load: exhibition-design
- Inputs: brief and research
- Deliver: narrative, zoning, visitor journey and image list
- Complete when: the executable plan exists
```

这是一种写作约定，不是硬 schema。Primary 读取全文后按照含义执行。

## 6. 默认工作流

Dreamatic 内置 `default-design-workflow`。

当用户没有明确指定其他工作流时，Primary 必须加载并执行它。它封装当前已经稳定的能力：

- 自动判断现有四个设计方向
- 按设计方向澄清需求
- `resolvedScope`
- `domainContext`
- Research -> Planner -> Designer -> Critic
- 五份默认计划文件
- PNG 图片集
- `00-gallery.html`
- Critic 失败后的一次修复
- `export_package`

这些字段和文件属于默认工作流，不是所有 Dreamatic 工作流的全局要求。

## 7. 新专业 Skill 接入默认工作流

用户可以只添加专业 Skill，而不改变阶段顺序。

例如用户安装 `fashion-design` 并明确要求使用它：

1. Primary 仍运行 `default-design-workflow`。
2. Primary 不把任务强制归入现有四类。
3. Primary 将 `fashion-design` 作为本轮专业 Skill。
4. Research、Planner、Designer 和 Critic 在各自阶段按需加载它。
5. 专业 Skill 正文决定调研重点、规划因素、产物建议和评价方法。

如果专业 Skill 没有提供某些阶段所需信息，基础 persona 使用通用能力补足，而不是要求 Skill 必须拥有 `domainContext`。

## 8. Primary 的工作流选择

Primary 按以下顺序处理：

1. 提取用户明确点名的 Skill。
2. 判断用户是否明确要求其中某个 Skill 控制工作流。
3. 如果是，加载该 Skill 并按正文编排。
4. 如果不是，把点名 Skill 作为补充知识，并加载 `default-design-workflow`。
5. 用户没有点名工作流时，加载 `default-design-workflow`。
6. 用户指定的 Skill 不存在时，报告未找到并列出名称相近的 Skill，不静默替换。

当前 `/design` 入口只允许工作流调用四个通用基础角色：

- `design-research`
- `design-planner`
- `design-designer`
- `design-critic`

工作流可以重排、跳过或重复调用这些角色，但不能通过正文声明新的
persona，也不能扩大 `design-primary` 的 `spawn_allowlist`。其他已经注册
的 subagent 不会自动获得当前设计入口的派生权限。

## 9. 基础 Persona

### 9.1 `design-primary`

负责：

- 理解用户意图
- 选择并加载工作流
- 初始化 run
- 按工作流编排阶段
- 向子智能体传递阶段目标和推荐 Skill
- 验证阶段交付
- 处理阻塞、修复和最终汇报

它不再写死四类设计和唯一阶段顺序。

### 9.2 `design-research`

负责：

- 根据阶段任务搜集、验证和整理证据
- 建立需要的参考资料库
- 加载父级指定或与任务匹配的 Skill
- 返回研究产物、来源和未解决问题

它不再假定一定存在 `domain_type`、`domainContext` 或固定研究文件。

### 9.3 `design-planner`

负责：

- 把 brief、研究结果和工作流要求转成可执行计划
- 明确交付、约束、一致性策略和验收方法
- 加载当前任务需要的专业 Skill

它不再全局强制五份固定文件；默认工作流仍然可以要求这五份文件。

### 9.4 `design-designer`

负责：

- 读取阶段计划并生成实际设计产物
- 使用可用工具维护视觉一致性
- 根据当前 Skill 采用专业设计方法
- 返回产物路径和执行结果

它不再固定读取当前四类映射。

### 9.5 `design-critic`

负责：

- 读取工作流验收要求和相关 Skill
- 执行通用 lint 与专业评价
- 给出通过、修复或阻塞结论

它不再要求评价字段必须来自 `domainContext`。

## 10. 阶段传递

Primary 传给子智能体的任务使用轻量自然语言外壳：

```text
Workflow skill: default-design-workflow
Stage: research
Run id: example-run
Run dir: D:\...\example-run

Goal:
完成本阶段的研究目标。

Load these skills:
- product-design
- accessibility-design

Inputs:
- brief.json
- 用户提供的参考链接

Expected outputs:
- 工作流要求的研究产物

Completion:
- 输出存在并向 Primary 报告结果
```

只有 `workflow skill`、`stage`、`run id`、`run dir` 和阶段目标是基础传递信息。其他内容由工作流决定。

默认工作流可以继续传递：

- `resolvedScope`
- `domainContext`
- `domain_type`
- 固定输出路径

新工作流不需要提供这些字段。

## 11. Run 与 Bus

`run_init` 保留稳定目录作为通用工作区，但扩展工作流不必使用其中每个目录。

通用 run 信息：

```json
{
  "runId": "string",
  "runDir": "string",
  "brief": "raw user brief",
  "workflowSkill": "skill name",
  "context": {}
}
```

默认工作流可以在 `context` 或兼容字段中保存 `resolvedScope` 和 `domainContext`。

Bus 保留统一消息外壳：

```json
{
  "runId": "string",
  "from": "registered agent id",
  "to": "registered agent id or all",
  "type": "string",
  "phase": "workflow-defined stage name",
  "summary": "string",
  "artifactRefs": [],
  "payload": {}
}
```

当前消息类型继续兼容：

- `research_done`
- `plan_done`
- `design_done`
- `evaluator_pass`
- `evaluator_fail`

扩展工作流可以使用自己的消息类型和阶段名称。发送者与接收者根据 Agent Registry 动态验证，不再写死五个角色常量。

## 12. Skill 发现机制

现有 SkillRegistry 已经能够扫描：

- `.myharness/skills/`
- 用户全局 `.myharness/skills/`
- 项目 `.claude/skills/`
- 用户全局 `.claude/skills/`

核心列表继续只依赖 `name`、`description` 和 `source`。可选 metadata 原样保留给配置界面或作者查看，但不参与是否允许加载的判断。

`use_skill` 始终按名称读取当前磁盘上的完整内容。因此用户明确提供准确名称时，新 Skill 即使没有分类也可以加载。

为了让会话创建后安装的新 Skill 也能被发现，系统始终注册只读
`list_skills` 工具。它会重新扫描当前磁盘上的 Skill，并返回名称、
描述和来源；这是一项发现能力，不是分类系统。

## 13. 第一版不做的事情

- 不建立 Skill 类型白名单。
- 不要求结构化 DAG。
- 不让工作流 Skill扩大 persona 权限。
- 不根据关键词擅自切换第三方工作流。
- 不建立图形化工作流编辑器。
- 不允许工作流 Skill 引入四个基础角色之外的新子智能体。
- 不要求所有旧 Skill 重写 metadata。
- 不立即删除默认工作流的兼容字段和目录。

## 14. 实施顺序

1. 创建 `default-design-workflow`，完整保留当前稳定行为。
2. 将 `/design` 改成通用入口。
3. 将 Primary 改成描述驱动的工作流选择和编排者。
4. 依次通用化 Research、Planner、Designer、Critic。
5. 让 `run_init` 接受通用 workflow/context，同时保留旧参数。
6. 让 Bus 动态接受已注册 persona、自定义阶段和消息类型。
7. 增加会话内 Skill 列表刷新能力。
8. 添加默认回退和自定义工作流测试。

## 15. 兼容性验收

### 场景 A：没有指定 Skill

加载 `default-design-workflow`，当前四类流程和产物保持稳定。

### 场景 B：指定一个专业 Skill

使用默认工作流，各阶段按需加载该 Skill，不强迫归入现有四类。

### 场景 C：指定一个新工作流 Skill

Primary 读取正文并按其阶段调用基础 persona，不强迫提供 `domainContext` 或固定五份计划文件。

### 场景 D：一个 Skill 同时包含工作流和专业知识

用户明确要求它控制工作流时，Primary 直接按正文执行，不要求拆成两个 Skill。

### 场景 E：无 metadata Skill

只要 name 和 description 有效，就能被发现、点名和加载。

### 场景 F：自定义 metadata Skill

未知字段原样保留，不影响加载。

### 场景 G：工作流重复使用角色

Research -> Planner -> Designer -> Critic -> Designer -> Critic 可以串行执行。

### 场景 H：不存在的 Skill

系统明确报告并提供相近可选项，不静默运行其他 Skill。
