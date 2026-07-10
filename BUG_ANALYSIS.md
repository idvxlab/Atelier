# MyHarnessPy Bug 与改进记录

记录日期：2026-07-10

本文档用于记录当前发现的问题、可能原因和后续修复方向。这里先做分析和归档，不直接实施改动。

## 1. 子智能体产生后前端不立即显示

### 现象

主 Agent 调用 `spawn_agent` 或 `spawn_agents` 创建子智能体后，前端左侧会话树不会立刻出现新的子会话。用户需要手动刷新页面或重新拉取会话列表后才能看到。

### 可能原因

- 后端创建子 Agent 时已经写入了 `parent_session_id`、`spawn_depth`、`display_name` 等 metadata，但没有向前端推送“会话树变化”事件。
- 当前 WebSocket 主要推送当前 session 的 token、message、state、question、queue 等事件，可能没有专门的 `session.created` / `session.tree_changed` / `subagent.created` 事件。
- 前端的 `loadSessions()` 可能只在页面初始化、手动刷新、切换会话时调用；子 Agent 创建成功后没有自动重新请求 `/sessions`。
- `pending_spawns` 能显示父 Agent 正在等待的子任务，但它不等同于左侧 session tree 的数据源，所以 pending 状态更新了，不一定触发 session tree 更新。

### 验证点

- 查看 `spawn_agent.py` 中子 Agent 创建后是否调用了父 engine 的状态通知。
- 查看 `api/ws.py` 是否有 session tree 相关事件。
- 查看 `static/index.html` 是否在收到 `pending_spawns` 或 `state` 事件时重新加载 session list。
- 复现时观察 Network：子 Agent 创建后前端是否重新请求 `/sessions`。

### 修复方向

- 在子 Agent 创建成功后推送一个明确事件，例如 `session.created` 或 `session.tree_changed`。
- 前端收到该事件后调用 `loadSessions()`，只刷新左侧会话树，不影响当前消息流。
- 或者在 state snapshot 中检测 `pending_spawns` 新增子会话时触发轻量刷新。

### 优先级

高。这个问题会直接影响多 Agent 功能的可见性，用户容易误以为子 Agent 没有创建成功。

## 2. Plan 功能不明显，Task 状态表达弱

### 现象

当前系统虽然有 `todo_write`，也有 `pending_commands`、`pending_spawns`、session state 等运行状态，但用户很难直观看到“当前计划是什么、每一步做到了哪里”。

### 可能原因

- `todo_write` 目前只是工具层的内存结构，存在 `_TODO_STORE` 中，没有专门 UI 展示。
- todo 状态没有进入 `GET /sessions/{id}/state` 的标准 snapshot，因此前端无法稳定渲染。
- 当前 `TaskRecord / TaskStatus` 分散在多个概念里：`pending_commands`、`pending_spawns`、`EngineState`、tool result、todo list，没有统一任务模型。
- `PlanState` 还不是一等对象。模型可以调用 `todo_write`，但系统没有把它提升为会话侧边栏或消息区中的计划面板。

### 验证点

- 检查 `todo_tool.py`：当前 todo 是否只存在内存，是否没有持久化。
- 检查 state snapshot：是否返回 todo list。
- 检查前端是否有 plan/todo panel。

### 修复方向

- 增加真正的 Plan UI，例如消息区右侧或顶部显示当前 todo list。
- 把 `todo_write` 的结果同步进 AgentEngine state snapshot。
- 将 todo 从 `_TODO_STORE` 迁移到 session metadata 或单独 SQLite 表，避免刷新或重启丢失。
- 引入轻量 `PlanState`：
  - `plan_id`
  - `session_id`
  - `items`
  - `status`
  - `updated_at`
- 引入更明确的 `TaskRecord / TaskStatus`，用于记录子任务、后台任务、排队任务，而不是只靠 pending list。

### 优先级

中高。它不一定阻塞主流程，但会影响“智能体在按计划工作”的可解释性和展示效果。

## 3. 当前主智能体不够通用，需要重构为 builder / planner 等角色

### 现象

现有 persona 包括 `coder`、`researcher`、`strict-reviewer`、`default` 等，但更像简单身份描述，不够接近通用 Agent 产品里的主智能体角色。

希望改成更清晰的角色体系，例如：

- `builder`：负责完整实现、修改文件、运行测试。
- `planner`：负责分析、拆解、设计方案，不直接改代码。
- `reviewer`：负责审查风险、bug、缺失测试。
- `researcher`：负责搜索、调研、整理资料。
- `docs`：负责文档书写。

### 可能原因

- 当前 persona 的 system prompt 较短，只描述风格，没有充分定义工作边界、工具权限、何时拆分任务、何时使用子 Agent。
- `allowed_tools` 多数为 `null`，没有体现不同主智能体的权限差异。
- “主智能体”和“子智能体”的角色边界还没有被明确建模，例如哪个 persona 可以作为 primary，哪个只适合作为 subagent。
- 目前 UI 里 persona 只是一个选项，没有呈现 builder/planner/reviewer 这类工作流入口。

### 参考材料

可参考：

- `D:\GitHub\test_opencode\helix - 副本\.opencode\agent\docs.md`
- `D:\GitHub\test_opencode\helix - 副本\.opencode\agent\triage.md`
- `D:\GitHub\test_opencode\helix - 副本\packages\web\src\content\docs\*\agents.mdx`

helix / opencode 的思路是：agent 不只是语气，而是带有 mode、tools、model、permission、description、hidden 等配置。文档里也提到常见角色：build agent、plan agent、review agent、debug agent、docs agent。

### 修复方向

- 新增一组更通用的 persona：
  - `builder.md`
  - `planner.md`
  - `reviewer.md`
  - `debugger.md`
  - `docs-writer.md`
- 为不同 persona 写清：
  - 适用场景
  - 工作流程
  - 是否允许写文件
  - 是否允许 shell/powershell
  - 是否优先使用 `todo_write`
  - 是否允许 `spawn_agent(s)`
  - 是否应该调用 `ask_user`
- 将 persona frontmatter 扩展为更接近 agent config：
  - `mode: primary | subagent | all`
  - `hidden: true | false`
  - `provider`
  - `allowed_tools`
  - `approval_mode` 默认建议
- UI 上把“新建会话”从普通 persona 下拉，升级为“选择主智能体”。

### 优先级

中。它影响产品形态和汇报观感，但需要谨慎设计，避免改了 persona 后破坏当前使用习惯。

## 4. 在必要位置加入 hook

### 现象 / 目标

当前系统已经有 events 和 WebSocket 推送，但还没有统一 hook 机制。希望在关键生命周期点加入 hook，让系统可以在不改主循环的情况下插入扩展逻辑。

### 可能需要 hook 的位置

- `before_session_create`
- `after_session_create`
- `before_user_message`
- `after_user_message`
- `before_llm_call`
- `after_llm_call`
- `before_tool_call`
- `after_tool_call`
- `before_spawn_agent`
- `after_spawn_agent`
- `before_compress`
- `after_compress`
- `on_state_transition`
- `on_error`

### 可能原因

- 当前 EventEmitter 更偏观测和前端通知，不适合做可插拔扩展。
- 一些需求已经开始依赖 hook 思路，例如：
  - 子 Agent 创建后刷新会话树。
  - 工具调用前做安全检查。
  - skill 使用过频时做拦截或降权。
  - LLM 调用前统一注入诊断信息。
  - 任务完成后自动生成 summary/title。

### 修复方向

- 增加 `HookRegistry` 或 `HookManager`。
- hook 输入使用结构化对象，例如 `HookEvent`。
- hook 输出使用结构化结果，例如 `HookResult`：
  - `continue`
  - `modify_payload`
  - `block`
  - `emit_event`
- 先做内部 hook，不急着做用户插件系统。
- 第一批 hook 可优先服务：
  - session tree 刷新
  - skill 使用节流
  - tool 调用审计
  - 自动命名

### 优先级

中。hook 本身不是单点 bug，但可以解决多个扩展能力都要侵入主循环的问题。

## 5. Skill 使用有时过于频繁

### 现象

模型有时会过于积极地调用 `use_skill`。即使任务只是普通问题，也可能加载 skill，导致上下文增加、工具调用变多、回答变慢。

### 可能原因

- 当前 system prompt 中列出了所有 skill 的名称和描述，并告诉模型可以调用 `use_skill` 加载详细说明。
- `use_skill` 的工具描述可能偏鼓励式：只要请求匹配 skill 描述就调用。
- 缺少“不要调用 skill”的负面条件，例如简单问答、一次性小修改、用户明确不需要流程化处理时不调用。
- skill 描述可能过宽，导致模型认为很多任务都匹配。
- 没有 per-session 或 per-round 的 skill 使用记忆，模型可能重复加载同一个 skill。
- 没有 hook 或 policy 对 skill 调用做节流。

### 参考材料

可参考 helix / opencode 的 agent/skill 思路：

- agent 更明确地区分角色和工具边界。
- skill/agent 描述短而精确，避免把所有通用任务都吸进去。
- 某些内部 agent 可以 hidden，只由任务工具触发，不在普通选择中暴露。

### 修复方向

- 修改 skill addendum 规则：
  - 只有当任务明确属于某 skill 的专业流程时才调用。
  - 简单问题、普通代码解释、短文档修改不要调用 skill。
  - 同一个 session 中同一 skill 已加载过时，优先复用已有上下文，不重复调用。
- 在 `use_skill` 增加调用记录：
  - session_id
  - skill_name
  - loaded_at
  - reason
- 在 `before_tool_call` hook 中对 `use_skill` 做节流：
  - 同一轮不重复加载同一 skill。
  - 短任务默认拒绝或要求模型先说明理由。
- 调整 skill 描述，让它更窄、更像触发条件，而不是宣传语。
- UI 或日志中显示 skill 调用原因，方便调试哪些 skill 过度触发。

### 优先级

中高。这个问题会影响 token 成本、响应速度和模型稳定性，也会让用户感觉 Agent “小题大做”。

## 6. 缺少全局持久 PlanState

### 现状

当前系统有 `todo_write`，可以让模型在 session 内维护一个 todo list。但它主要是工具层的内存状态，不是全局、持久、可查询、可恢复的一等计划对象。

也就是说，现在的计划更像“模型当前这轮工作的临时清单”，还不是系统级 `PlanState`。

### 缺口

- todo 不一定持久化到 SQLite。
- 刷新页面后前端没有稳定 Plan 面板。
- 不同 session / sub-agent 的计划没有统一关联。
- 没有 plan_id、owner_session_id、parent_plan_id 等结构。
- 没有计划历史、计划变更记录、计划完成率。
- 没有把计划和 TaskRecord / 子 Agent 结果打通。

### 参考方向

可以参考 `D:\GitHub\test_opencode\helix - 副本` 里 agent config 的思路：不同 agent 具有不同 mode、tools、permission。我们的 PlanState 可以配合 planner/builder 角色使用：

- `planner` 负责生成和维护计划。
- `builder` 按计划执行。
- `reviewer` 检查计划完成质量。
- 子 Agent 可以挂到某个 plan item 下。

### 设计建议

新增持久化结构：

- `PlanState`
  - `plan_id`
  - `session_id`
  - `title`
  - `status`
  - `items`
  - `created_at`
  - `updated_at`
- `PlanItem`
  - `item_id`
  - `plan_id`
  - `content`
  - `status`
  - `assigned_session_id`
  - `result_message_id`

状态建议：

- `pending`
- `in_progress`
- `blocked`
- `completed`
- `cancelled`

### 修复方向

- 先把 `todo_write` 升级为写入 SQLite 或 session metadata。
- 在 `/sessions/{id}/state` 中返回当前 plan。
- 前端增加 Plan UI。
- 子 Agent 创建时可选择绑定到某个 plan item。
- 后续再把 PlanState 从 session 层扩展为跨 session 的任务图。

### 优先级

中高。它会显著提升任务可解释性，尤其适合汇报“Agent 如何规划和执行”。

## 7. 缺少独立持久 MemoryStore

### 现状

当前系统有 SQLite session 持久化、messages 保存、checkpoint、compression summary，但这些主要服务于“会话恢复”。它还不是独立的长期记忆系统。

换句话说，系统能记住某个 session 发生过什么，但还没有抽取出跨会话可复用的 MemoryEntry。

### 缺口

- 没有独立 `MemoryEntry` 表。
- 没有跨 session 的用户偏好、项目事实、长期经验沉淀。
- 没有 memory 的写入策略和读取策略。
- 没有 memory 召回、过期、置信度、来源追踪。
- compression summary 不能直接等同于长期记忆，因为它是为了省上下文，不是为了沉淀知识。

### 参考方向

可以参考 helix / opencode 的规则文件和 agent 配置思路：项目规则、agent 说明、命令和工具配置都可以作为上下文来源。我们的 MemoryStore 可以分层：

- project memory：项目长期事实和约定。
- user memory：用户偏好和工作习惯。
- session memory：当前会话总结。
- agent memory：某类 agent 的经验或默认策略。

### 设计建议

新增结构：

- `MemoryEntry`
  - `memory_id`
  - `scope`
  - `kind`
  - `content`
  - `source_session_id`
  - `source_message_id`
  - `confidence`
  - `tags`
  - `created_at`
  - `updated_at`
  - `expires_at`

scope 可以是：

- `global`
- `project`
- `user`
- `session`
- `agent`

kind 可以是：

- `preference`
- `fact`
- `decision`
- `summary`
- `lesson`

### 修复方向

- 先增加 MemoryStore 抽象和 SQLite 实现。
- 增加 `remember` / `recall` 工具，或者先只做内部 API。
- 在压缩、任务完成、用户明确要求记住时写入 memory。
- 在构建 prompt 时按 scope 召回少量相关 memory。
- 前端后续可以增加 Memory 管理面板。

### 优先级

中。它不是当前 bug，但会决定系统能否从“会话型 Agent”升级为“长期协作型 Agent”。

## 8. 缺少 TeamMember / Agent Registry

### 现状

当前系统已经有多 Agent 能力：`spawn_agent`、`spawn_agents`、`parent_session_id`、`spawn_depth`、子会话树。但子 Agent 主要是运行时临时创建的 session，还没有长期存在的团队成员模型。

也就是说，现在有“子 Agent 会话”，但没有“团队成员注册表”。

### 缺口

- 没有 `TeamMember` 或 `AgentProfile` 这样的持久对象。
- builder、planner、reviewer、debugger、docs writer 还只是 persona 设想，不是系统级 agent registry。
- 没有定义哪些 agent 可作为 primary，哪些只作为 subagent。
- 没有 agent 可见性，如 hidden/internal。
- 没有 agent-to-agent 调用权限，例如 planner 是否允许调用 builder。
- 没有 agent 默认工具、默认模型、默认 approval mode。

### 参考方向

可以参考 `D:\GitHub\test_opencode\helix - 副本` 的 agent 配置方式。helix / opencode 里 agent 可以有：

- `mode: primary | subagent | all`
- `hidden: true | false`
- `model`
- `tools`
- `permission`
- `description`
- `color`

这些概念可以映射到 MyHarnessPy 的 persona / multi-agent 系统里。

### 设计建议

新增结构：

- `AgentProfile`
  - `agent_id`
  - `name`
  - `description`
  - `mode`
  - `hidden`
  - `provider`
  - `system_prompt`
  - `allowed_tools`
  - `default_approval_mode`
  - `color`
  - `can_spawn`
  - `spawn_allowlist`

常见内置 agent：

- `builder`：负责实现和修改，工具权限较完整。
- `planner`：负责分析和计划，默认不写文件。
- `reviewer`：负责审查和风险发现，偏只读。
- `debugger`：负责定位问题，可读文件和运行命令。
- `docs-writer`：负责文档，允许读写文档但限制 shell。

### 修复方向

- 先把 persona frontmatter 扩展为 agent profile。
- 新建 builder/planner/reviewer/debugger/docs-writer 几个 markdown 配置。
- 前端把“Persona”概念逐步改成“Agent”或“主智能体”。
- `spawn_agent` 支持按 agent profile 创建子 Agent，而不是只传 system_prompt/tools。
- 增加 agent 调用权限，避免任意 agent 随意创建任意高权限子 Agent。

### 优先级

中高。它会让多 Agent 功能从“能创建子会话”升级为“有稳定团队角色的 Agent 系统”。

## 后续处理建议

建议先按这个顺序处理：

1. 修复子 Agent 创建后前端不刷新的问题。
2. 增加 Plan UI，把 `todo_write` 变成可见计划。
3. 把 `todo_write` 升级为持久 PlanState。
4. 设计 builder / planner / reviewer 等主智能体 persona，并逐步升级为 AgentProfile / TeamMember。
5. 引入最小 HookManager，为 session tree 刷新和 skill 节流服务。
6. 调整 skill 调用策略，减少过度加载。
7. 增加独立 MemoryStore，先做 project/session scope，再扩展 user/global scope。
