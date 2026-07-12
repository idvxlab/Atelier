# MyHarnessPy 开发者文档

本文档面向继续开发、维护和汇报 MyHarnessPy 的开发者。它参考了 opencode 文档的组织方式，把一个 Agent Harness 拆成“配置、Agent、工具、权限、上下文、记忆、多 Agent、前端、扩展接口”等模块来说明；具体实现以本仓库当前代码为准。

参考阅读：

- opencode 中文文档：https://opencode.ai/docs/zh-cn
- 本项目架构汇报文档：[HARNESS_ARCHITECTURE_REPORT.md](./HARNESS_ARCHITECTURE_REPORT.md)
- Bug 和改进记录：[BUG_ANALYSIS.md](./BUG_ANALYSIS.md)
- 近期计划：[ROADMAP.md](./ROADMAP.md)

本文档的组织方式借鉴了 opencode 这类 Agent 工具文档的常见结构：先说明项目定位和运行方式，再讲 provider、agent、tools、permissions、MCP、custom command/skill 等扩展点。区别是：opencode 是成熟产品文档，本文件是 MyHarnessPy 的开发者说明，因此每一章都会落回本项目的真实代码文件和当前实现边界。

## 1. 项目定位

MyHarnessPy 是一个自建 Agent Harness。它不是简单聊天页面，而是一个同时支持 CLI 和 Web 的 Agent 运行时，负责把大模型、工具调用、权限审批、上下文压缩、Skill、长期记忆、计划、子 Agent、会话树和 WebSocket 状态推送组织到同一套框架里。

核心目标是：

- 让模型能使用真实工具完成任务，而不只是生成文本。
- 让每个会话拥有可恢复的状态、消息、标题、权限和上下文。
- 让复杂任务能被计划、排队、拆给子 Agent，并在前端可见。
- 让用户能配置 provider、persona、工具、审批模式、MCP 和 Skill。
- 让开发者能继续扩展工具、Agent、记忆、计划和运行时 hook。

核心入口文件：

- [api/rest.py](./api/rest.py)：Web/REST API 入口。
- [api/ws.py](./api/ws.py)：WebSocket 实时推送。
- [cli.py](./cli.py)：命令行入口。
- [harness/factory.py](./harness/factory.py)：构建 AgentEngine 的统一入口。
- [harness/engine/engine.py](./harness/engine/engine.py)：单个会话的状态管理。
- [harness/engine/loop.py](./harness/engine/loop.py)：ReAct 主循环。
- [static/index.html](./static/index.html)：当前 Web 前端。

## 2. 如何运行

项目依赖 Python 3.11+。当前本机常用解释器是：

```powershell
D:\Anaconda\python.exe
```

安装依赖：

```powershell
D:\Anaconda\python.exe -m pip install -e .[dev]
```

启动 Web 服务：

```powershell
D:\Anaconda\python.exe -m uvicorn api.rest:app --host 127.0.0.1 --port 8000 --reload
```

启动 CLI：

```powershell
D:\Anaconda\python.exe cli.py
```

运行测试：

```powershell
D:\Anaconda\python.exe -m pytest
```

常用针对性测试：

```powershell
D:\Anaconda\python.exe -m pytest tests/test_engine.py tests/test_tools.py
D:\Anaconda\python.exe -m pytest tests/test_spawn_agent.py
D:\Anaconda\python.exe -m pytest tests/test_storage.py tests/test_tasks.py
```

## 3. 配置系统

全局配置主要在 [config.yaml](./config.yaml)。加载逻辑在 [harness/config.py](./harness/config.py)。

配置分为几类：

- `default_provider`：新会话默认使用哪个 provider。
- `providers`：模型供应商配置。
- `engine`：主循环最大轮数等。
- `compression`：上下文压缩配置。
- `storage`：状态存储后端。
- `tools`：启用工具、审批工具、工具输出上限。
- `mcp_servers`：MCP Server 配置。

环境变量通过 `.env` 或系统环境注入。配置里支持 `${ENV_NAME}` 展开，例如：

```yaml
openai-hub:
  name: openai-compatible
  model: "${OPENAI_HUB_MODEL}"
  api_key: "${OPENAI_HUB_API_KEY}"
  base_url: "${OPENAI_HUB_BASE_URL}"
```

Provider 名称支持兼容别名，例如 `my-361api` 会归一到 `361api-openai`。实现见 `HarnessConfig._normalize_provider_name()`。

## 4. Provider 与模型层

模型层把不同模型服务商统一成同一个接口。相关文件：

- [harness/llm/base.py](./harness/llm/base.py)
- [harness/llm/registry.py](./harness/llm/registry.py)
- [harness/llm/openai_provider.py](./harness/llm/openai_provider.py)
- [harness/llm/anthropic_provider.py](./harness/llm/anthropic_provider.py)

Provider 对外暴露三个方法：

- `chat(messages, tools)`：普通工具调用式对话。
- `stream_chat(messages, tools, on_token)`：流式输出。
- `complete(prompt)`：轻量补全，用于标题、摘要等。

当前支持：

- OpenAI-compatible：OpenAI Hub、361API、BLTCY OpenAI 等兼容 `/chat/completions` 的服务。
- Anthropic：Claude 系列。

`build_provider(cfg)` 根据 `ProviderConfig.name` 创建具体 provider。ReactLoop 不关心底层供应商，只调用统一接口。

## 5. AgentEngine 是什么

`AgentEngine` 是一个会话的单一事实源。它管理：

- `messages`
- `EngineState`
- 当前 provider/persona/agent_id
- question mode
- approval mode
- pending approval
- pending question requests
- pending command queue
- pending sub-agent queue
- title generation
- memory/plan store 引用
- WebSocket 监听器

状态机定义在 [harness/engine/state_machine.py](./harness/engine/state_machine.py)。主要状态：

- `WAITING_INPUT`：等待用户输入。
- `RUNNING`：主循环运行中。
- `WAITING_CONFIRMATION`：等待工具审批。
- `WAITING_INTERRUPT`：等待用户回答 ask_user 问题。
- `COMPLETED`：当前任务完成。
- `ERROR`：运行出错。

REST 层和 CLI 不直接调用 LLM，而是调用 `engine.send_message()`。Engine 判断当前状态后，再决定是启动新循环还是把输入放入队列。

## 6. ReAct 主循环

ReAct 主循环在 [harness/engine/loop.py](./harness/engine/loop.py)。每轮大致流程：

1. 检查 cancel 信号。
2. 执行上下文压缩。
3. 从 ToolRegistry / PromptCache 获取工具 schema。
4. 调用 LLM。
5. 如果没有 tool call，追加 assistant 消息并结束。
6. 如果重复调用同一工具，LoopDetector 注入提醒，避免死循环。
7. 如果工具需要审批，进入 confirmation gate。
8. 并发执行本轮所有 tool call。
9. 验证 assistant tool_call 和 tool_result 的消息顺序。
10. 原子追加 assistant/tool 消息对。
11. 如果工具结果带 `is_interrupt=True`，抛出 `InterruptSignal`，由 Engine 暂停。
12. 在安全点处理运行中排队的用户输入。

这个设计的关键点是：工具调用协议不能被用户消息打断。assistant 发出 tool_call 后，必须紧跟对应 tool_result，否则 OpenAI-compatible API 会拒绝请求。因此运行中的新用户输入先进入 pending queue，等工具链闭合后再处理。

## 7. 构建一个 Engine 的流程

统一构建入口是 [harness/factory.py](./harness/factory.py) 的 `build_engine()`。

构建过程：

1. 创建 `EventEmitter(session_id)`。
2. 准备 `MemoryStore` 和 `PlanStore`，没有传入时使用内存后端。
3. 根据 provider config 创建 LLM provider。
4. 根据 compression config 创建 `ContextCompressor`。
5. 扫描 skills，构建 skill addendum。
6. 拼接 system prompt：
   - 项目上下文 `MYHARNESS.md`
   - persona system prompt
   - skill 列表
   - 强制 think 的推理规则
   - todo_write 计划规则
   - 工具失败恢复规则
   - question/noquestion mode 规则
7. 按 `config.tools.enabled` 和 persona `allowed_tools` 注册工具。
8. 如果存在 skills，注册 `use_skill`。
9. 如果未达到最大子 Agent 深度，注册 `spawn_agent` 和 `spawn_agents`。
10. 创建 PromptCache、ToolExecutor、ReactLoop。
11. 创建 AgentEngine。
12. 如果 question mode 开启，注册 `ask_user`。

`build_engine_with_mcp()` 会先连接 MCP Server，把 MCP 工具注册进 ToolRegistry，再调用同样的构建逻辑。

## 8. Web / REST / WebSocket

REST API 在 [api/rest.py](./api/rest.py)。核心接口：

- `POST /sessions`：创建会话。
- `GET /sessions`：列出会话。
- `GET /sessions/{id}/state`：读取完整快照。
- `POST /sessions/{id}/messages`：发送消息。
- `PATCH /sessions/{id}/messages/{message_id}`：重写历史消息。
- `POST /sessions/{id}/cancel`：取消运行。
- `POST /sessions/{id}/confirm` / `deny`：审批工具。
- `PATCH /sessions/{id}/mode`：切换 question mode。
- `PATCH /sessions/{id}/approval-mode`：切换审批模式。
- `DELETE /sessions/{id}/pending/{index}`：取消排队输入或 pending sub-agent。
- `GET /memory` / `POST /memory` / `DELETE /memory/{entry_id}`：管理长期记忆。
- `/config/*`：管理 config、skills、personas、agents。
- `/commands` 和 `/sessions/{id}/commands/{command_id}`：命令系统。

WebSocket 在 [api/ws.py](./api/ws.py)。它订阅 Engine 的 message/token/state/event listener，把流式 token、状态变化、question、subagent.created 等事件推给前端。

前端在 [static/index.html](./static/index.html)。它不把本地缓存当真相，切换会话或刷新时会调用 `/state` 恢复状态。

## 9. 会话与持久化

存储抽象：

- [harness/storage/session.py](./harness/storage/session.py)：SessionStore。
- [harness/storage/checkpoint.py](./harness/storage/checkpoint.py)：CheckpointStore。
- [harness/storage/memory_store.py](./harness/storage/memory_store.py)：MemoryStore。
- [harness/storage/plan_store.py](./harness/storage/plan_store.py)：PlanStore。

后端实现：

- [harness/storage/backends/memory.py](./harness/storage/backends/memory.py)：内存实现。
- [harness/storage/backends/sqlite.py](./harness/storage/backends/sqlite.py)：SQLite 实现。

SQLite 里当前主要表：

- `sessions`：会话消息和 metadata。
- `checkpoints`：检查点。
- `memories`：长期记忆。
- `plans`：会话计划。
- `plan_items`：计划项。

Session metadata 存储：

- `provider`
- `persona`
- `question_mode`
- `approval_mode`
- `title`
- `display_name`
- `parent_session_id`
- `spawn_depth`
- `plan_item_id`

前端会话树通过 `parent_session_id` 和 `spawn_depth` 构建。

## 10. 工具系统

工具系统由三部分组成：

- [harness/types/tools.py](./harness/types/tools.py)：`ToolSchema` 和 `ToolParam`。
- [harness/tools/registry.py](./harness/tools/registry.py)：注册和发现工具。
- [harness/tools/executor.py](./harness/tools/executor.py)：执行工具、截断输出、处理中断、触发 hook。

内置工具在 [harness/tools/builtin](./harness/tools/builtin)。

当前常用工具：

- 文件：`read_file`、`write_file`、`edit_file`
- 搜索：`search`、`glob`、`grep`
- 终端：`shell`、`powershell`
- Web：`web_fetch`、`web_search`
- 推理与计划：`think`、`todo_write`
- 长期记忆：`memory`
- 用户协作：`ask_user`
- Skill：`use_skill`
- 多 Agent：`spawn_agent`、`spawn_agents`

新增工具步骤：

1. 在 `harness/tools/builtin/<name>.py` 新建工具文件。
2. 定义 `ToolSchema`。
3. 写 `async def` handler，参数名和 ToolParam 对齐。
4. 在 `harness/tools/builtin/__init__.py` 导出。
5. 在 `harness/factory.py` 的 `ALL_TOOLS` 注册。
6. 在 `config.yaml` 的 `tools.enabled` 启用。
7. 如需审批，加入 `tools.confirm_tools`。
8. 补测试。

工具 handler 应尽量返回字符串，错误也返回 `"Error: ..."`，不要让异常直接逃逸给模型。ToolExecutor 会兜底捕获异常并包装为 tool_result。

## 11. 工具输出限制与 Overflow

ToolExecutor 会按工具名查输出上限：

- 配置来源：`config.yaml` 的 `tools.limits`
- 默认值：`DEFAULT_LIMIT = 8000`

如果输出超过上限，ToolExecutor 会把完整输出放入 `OverflowStore`，返回一个引用：

```text
[Output exceeded 8000 char limit. Full output stored at ref:<id>]
```

这避免大型文件、网页或命令输出直接撑爆上下文。

## 12. 权限与审批

权限系统有三层：

### 12.1 工具是否可见

工具可见性由全局 `config.tools.enabled` 和 persona `allowed_tools` 共同决定：

- 如果 persona 没有 `allowed_tools`，使用全局 enabled。
- 如果 persona 有 `allowed_tools`，取 persona allowlist 与全局 enabled 的交集。

### 12.2 哪些工具需要审批

`config.tools.confirm_tools` 决定哪些工具触发 confirmation gate。当前通常是：

```yaml
confirm_tools:
  - shell
  - powershell
```

### 12.3 当前会话如何审批

`approval_mode` 是会话级设置：

- `ask`：命中 confirm_tools 时前端弹审批面板。
- `auto`：自动批准 confirm_tools，但保留事件记录。
- `full`：绕过 confirm_tools gate，相当于当前会话全权限。

`PATCH /sessions/{id}/approval-mode` 可以运行时切换。

persona 可以设置 `default_approval_mode`，创建会话时如果用户没有显式选择，后端会使用 persona 默认值。子 Agent 创建时也会应用 profile 的默认审批模式；如果 profile 没有默认值，则继承父 Agent 的审批模式。

## 13. Persona 与 AgentProfile

persona 文件位于 [.myharness/personas](./.myharness/personas)。解析逻辑在 [harness/skills.py](./harness/skills.py)，结构化成 AgentProfile 的逻辑在 [harness/agents.py](./harness/agents.py)。

推荐 persona 文件格式：

```markdown
---
name: planner
description: "负责拆解任务和维护计划"
mode: primary
hidden: false
provider: openai-hub
allowed_tools:
  - read_file
  - search
  - think
  - todo_write
default_approval_mode: ask
can_spawn: true
spawn_allowlist:
  - reviewer
  - docs-writer
color: "#58a6ff"
---

你是一个规划型 Agent...
```

字段含义：

- `name`：profile id。
- `description`：前端展示说明。
- `mode`：`primary`、`subagent`、`all`。
- `hidden`：是否隐藏。
- `provider`：覆盖默认 provider。
- `allowed_tools`：工具白名单。
- `default_approval_mode`：默认审批模式。
- `can_spawn`：是否允许创建子 Agent。
- `spawn_allowlist`：允许创建哪些子 Agent。
- 正文：system prompt。

当前 `AgentProfile` 还不是独立数据库对象，而是由 persona frontmatter 派生。

## 14. Skill 机制

Skill 是“工作流预设”，不是工具。它告诉 Agent 如何处理某类任务。

扫描路径优先级：

1. `.myharness/skills`
2. `~/.myharness/skills`
3. `.claude/skills`
4. `~/.claude/skills`

推荐目录结构：

```text
.myharness/skills/my-skill/SKILL.md
```

`SKILL.md` 格式：

```markdown
---
name: frontend-polish
description: "用于审查和优化前端 UI"
---

当用户要求改进前端体验时，按以下步骤工作...
```

构建 prompt 时，系统只注入 skill 的名称和 description。完整内容只有在模型调用 `use_skill(name=...)` 时才读取。这样可以避免启动时把所有 skill 内容塞进上下文。

当前 prompt 已经加入节流规则：简单问题、小修改、普通调试不要调用 skill；同一 session 不要反复加载同一 skill，除非任务变化明显。

## 15. Plan 与 Task

计划工具是 `todo_write`，实现位于 [harness/tools/builtin/todo_tool.py](./harness/tools/builtin/todo_tool.py)。

非简单任务时，system prompt 要求模型先调用 `think`，再调用：

```text
todo_write(action="set")
```

随后工作中用：

```text
todo_write(action="update")
```

更新计划项状态。

计划持久化：

- `todo_write` 会写入 `PlanStore`。
- 也会同步写 session metadata fallback。
- `GET /sessions/{id}/state` 返回 `todos`。

`PlanStore` 类型：

- `PlanState`
- `PlanItem`

SQLite 表：

- `plans`
- `plan_items`

Task 统一视图在 [harness/types/tasks.py](./harness/types/tasks.py)。`TaskRecord` 把三类状态统一到 `/state.tasks`：

- `plan_item`：来自 PlanStore 的计划项。
- `queued_command`：运行中输入队列。
- `subagent`：运行中的子 Agent。

当前边界：`TaskRecord` 是快照视图，不是独立持久化 TaskStore。

## 16. Memory 机制

MemoryStore 定义在 [harness/storage/memory_store.py](./harness/storage/memory_store.py)。工具实现是 [harness/tools/builtin/memory_tool.py](./harness/tools/builtin/memory_tool.py)。

MemoryEntry 字段：

- `entry_id`
- `content`
- `scope`
- `tags`
- `created_by_session`
- `created_at`
- `updated_at`
- `metadata`

添加 memory 的方式：

1. Agent 调用 `memory(action="add")`。
2. 用户在前端“长期记忆”面板手动新增，调用 `POST /memory`。

读取 memory 的方式：

1. Agent 主动调用 `memory(action="search" | "list" | "get")`。
2. 每次 Agent 运行前，`AgentEngine._build_memory_context_message_if_needed()` 会自动用最近用户输入搜索 MemoryStore，最多取 5 条，生成临时 system context 注入本轮。

临时 memory context 不会持久化到 messages。`_run_loop_guarded()` 会在 finally 里把这条临时 system message 移除后再保存 session。

当前边界：

- 不会自动总结对话并写入 Memory。
- 搜索是简单文本匹配，不是向量检索。
- 没有候选记忆审批流。
- 没有置信度、过期时间、source_message_id。

## 17. 多 Agent

多 Agent 工具位于 [harness/tools/builtin/spawn_agent.py](./harness/tools/builtin/spawn_agent.py)。

工具：

- `spawn_agent`：创建一个子 Agent，执行完成后返回结果。
- `spawn_agents`：并行创建多个子 Agent，用 `asyncio.gather` 等全部完成。

子 Agent 创建流程：

1. 检查最大深度 `MAX_SPAWN_DEPTH = 3`。
2. 检查父 AgentProfile 的 `can_spawn` 和 `spawn_allowlist`。
3. 生成 `sub_<hex>` session id。
4. 根据 task 生成 display name。
5. 如果指定 `agent`，加载对应 AgentProfile。
6. 应用子 Agent 的 system prompt、allowed_tools、provider、default_approval_mode。
7. 调用 `build_engine()` 创建子 AgentEngine。
8. 写入 session metadata：`display_name`、`spawn_depth`、`parent_session_id`、`persona`、`plan_item_id`。
9. 如果传入 `plan_item_id`，把父计划项绑定到子 session。
10. 在父 Engine 的 `pending_spawns` 里注册。
11. 调用 `sub_engine.run_to_completion()`。
12. 完成后从父 Engine 的 pending_spawns 移除。

前端通过 session tree 展示父子关系，通过 pending_spawns / tasks 展示正在运行的子任务。

## 18. ask_user 与人机协作

`ask_user` 是 interruptible tool，位于 [harness/tools/builtin/ask_user.py](./harness/tools/builtin/ask_user.py)。

它和普通工具不同：

- 工具被调用后立即返回一个带 `is_interrupt=True` 的结果。
- ToolExecutor 把它包装为 tool_result。
- ReactLoop 检测到 interrupt，抛出 `InterruptSignal`。
- AgentEngine 捕获后进入 `WAITING_INTERRUPT`。
- 前端展示 question card。
- 用户回答后，REST 接口把答案写回对应 tool_result。
- Engine 恢复主循环继续执行。

question mode 开启时，prompt 明确要求模型必须通过 `ask_user` 生成结构化问题，不允许直接用普通 assistant 文本问用户。

## 19. 上下文压缩

压缩逻辑在 [harness/engine/compression.py](./harness/engine/compression.py)。

配置：

```yaml
compression:
  token_window: 128000
  auto_trigger_ratio: 0.65
  micro_keep_recent: 6
  summary_provider: openai-hub-mini
```

两类压缩：

- micro compression：压缩旧工具结果，保留近期消息。
- auto compression：当估算 token 超过阈值时，用 summarizer 把旧消息总结成摘要。

注意：compression summary 是为了控制上下文，不等同于长期 Memory。Memory 是单独的 MemoryStore。

## 20. MCP

MCP 支持在 [harness/mcp](./harness/mcp)。

主要文件：

- `stdio_transport.py`：启动本地 MCP server 子进程，通过 stdin/stdout JSON-RPC 通信。
- `http_transport.py`：HTTP 风格远程 MCP transport。
- `client.py`：initialize、tools/list、tools/call。
- `bridge.py`：把 MCP 工具转成 Harness ToolSchema 并注册进 ToolRegistry。

配置示例：

```yaml
mcp_servers:
  filesystem:
    transport: stdio
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]
```

注册时可以加 namespace 前缀，例如 `filesystem__read_file`，避免多个 MCP server 工具重名。

## 21. Hook

Hook 机制在 [harness/hooks.py](./harness/hooks.py)，目前是轻量第一版。

已接入位置：

- `before_llm_call`
- `after_llm_call`
- `before_tool_call`
- `after_tool_call`

HookEvent 包含：

- `name`
- `session_id`
- `round_index`
- `payload`

HookResult 可以阻止执行或返回原因。当前 hook 更多是内部扩展点，还不是完整插件系统。

未来可以继续接入：

- before/after spawn
- before/after memory write
- before/after plan update
- before/after compression
- session.created / session.deleted

## 22. 命令系统

命令系统位于 [harness/commands](./harness/commands)。

用途：

- CLI 和 Web 中执行斜杠命令。
- 内置命令：help、tools、skills、personas、state、exit 等。
- 自定义命令可以是 prompt 模板，也可以要求参数。

REST 接口：

- `GET /commands`
- `POST /sessions/{session_id}/commands/{command_id}`

命令系统和工具系统不同：命令通常由用户主动触发，工具由模型通过 tool call 触发。

## 23. 前端结构

当前前端是单文件 [static/index.html](./static/index.html)。

主要区域：

- 左侧 session tree。
- 顶部 session title / persona / provider / approval mode。
- 消息流。
- approval panel。
- plan panel。
- queue panel。
- config panel。
- memory manager。
- new session modal。
- question card。

前端主要依赖：

- `GET /sessions`
- `GET /sessions/{id}/state`
- WebSocket `/sessions/{id}/ws`
- `/config/*`
- `/memory`

前端原则：后端是单一事实源。前端只做渲染和轻量 optimistic UI，不持久保存业务状态。

## 24. 如何新增一个 Provider

1. 在 `harness/llm` 下实现一个 `LLMProvider` 子类。
2. 实现：
   - `chat`
   - `stream_chat`
   - `complete`
3. 在 [harness/llm/registry.py](./harness/llm/registry.py) 里根据 `ProviderConfig.name` 分发。
4. 在 `config.yaml` 增加 provider 配置。
5. 补消息格式转换和工具 schema 转换测试。

如果新服务兼容 OpenAI chat completions，通常只需要新增 config，不需要写 provider。

## 25. 如何新增一个 Agent / Persona

在 `.myharness/personas/<name>.md` 新建文件：

```markdown
---
name: builder
description: "负责实现和验证"
mode: primary
hidden: false
provider: openai-hub
allowed_tools:
  - read_file
  - write_file
  - edit_file
  - search
  - shell
  - think
  - todo_write
default_approval_mode: ask
can_spawn: true
spawn_allowlist:
  - reviewer
---

你是一个实现型 Agent...
```

保存后：

- `/config/personas` 会列出它。
- `/config/agents` 会把它转换成 AgentProfile。
- 新建会话可选择它。
- `spawn_agent(agent="<name>")` 可用它创建子 Agent。

## 26. 如何新增一个 Skill

在 `.myharness/skills/<name>/SKILL.md` 新建：

```markdown
---
name: api-review
description: "用于审查 API 设计和错误处理"
---

当用户要求审查 API 时：

1. 先读路由定义。
2. 检查错误码、输入校验、状态持久化。
3. 输出风险和建议。
```

Skill 不需要注册进 `config.yaml`。只要扫描路径中存在，就会出现在 prompt 的 skill 列表里，并可通过 `use_skill` 按需加载。

## 27. 如何排查常见问题

### 27.1 Provider 401

检查：

- `.env` 里对应 API key 是否存在。
- `config.yaml` provider 的 `api_key` / `api_key_env` 是否匹配。
- `base_url` 是否是当前服务商实际地址。
- 新建会话时选中的 provider 是否是你想用的 provider。

### 27.2 模型没有调用 plan

检查：

- `todo_write` 是否在 `config.tools.enabled`。
- 当前 persona 的 `allowed_tools` 是否包含 `todo_write`。
- `/state.todos` 和 `/state.tasks` 是否为空。
- 用户任务是否被 `_looks_nontrivial_for_plan()` 判断为复杂任务。

### 27.3 子 Agent 不显示

检查：

- 子 session metadata 是否有 `parent_session_id`。
- WebSocket 是否收到 `subagent.created`。
- 前端是否重新调用 `loadSessions()`。
- `/sessions` 列表里子 session 是否存在。

### 27.4 Memory 没有召回

检查：

- MemoryStore 是否有相关内容。
- 当前 query 是否和 memory content/tags/scope 有文本重叠。
- 当前实现不是向量搜索，语义相近但文本不重叠可能搜不到。
- `EngineConfig.memory_store` 是否传入。

### 27.5 工具报“not found”

检查：

- `harness/factory.py` 的 `ALL_TOOLS` 是否注册。
- `config.yaml tools.enabled` 是否启用。
- persona `allowed_tools` 是否把它过滤掉。
- MCP 工具是否带 namespace 前缀。

## 28. 当前边界和后续方向

已经实现第一版：

- CLI / Web / REST / WebSocket
- Provider registry
- ReAct loop
- ToolRegistry / ToolExecutor
- approval mode
- question mode / ask_user
- Skill 扫描与按需加载
- SQLite session 持久化
- PlanStore / todo_write
- MemoryStore / memory 工具 / 自动召回
- spawn_agent / spawn_agents
- session tree
- TaskRecord 快照视图
- MCP stdio / HTTP 接入
- Config CRUD

仍待完善：

- TaskRecord 还不是持久 TaskStore。
- Memory 还没有候选记忆审批流。
- Memory 搜索还不是向量检索。
- TeamMember 还没有独立持久模型。
- Hook 机制还没覆盖所有生命周期点。
- Skill 使用节流还主要靠 prompt 规则，不是强制 policy。
- 前端仍是单文件，长期可拆组件。

## 29. 代码地图

| 领域 | 文件 |
| --- | --- |
| Web API | `api/rest.py` |
| WebSocket | `api/ws.py` |
| CLI | `cli.py` |
| Engine 构建 | `harness/factory.py` |
| 主状态机 | `harness/engine/engine.py` |
| ReAct 循环 | `harness/engine/loop.py` |
| 上下文压缩 | `harness/engine/compression.py` |
| Prompt 缓存 | `harness/engine/prompt_cache.py` |
| Provider | `harness/llm/*` |
| 工具注册执行 | `harness/tools/registry.py`, `harness/tools/executor.py` |
| 内置工具 | `harness/tools/builtin/*` |
| Skill / Persona | `harness/skills.py`, `.myharness/*` |
| AgentProfile | `harness/agents.py` |
| Session 存储 | `harness/storage/session.py`, `harness/storage/backends/*` |
| Plan | `harness/storage/plan_store.py`, `harness/tools/builtin/todo_tool.py` |
| Memory | `harness/storage/memory_store.py`, `harness/tools/builtin/memory_tool.py` |
| Task 快照 | `harness/types/tasks.py` |
| MCP | `harness/mcp/*` |
| Commands | `harness/commands/*` |
| 前端 | `static/index.html` |
