# MyHarnessPy 智能体 Harness 架构汇报文档

## 0. 项目定位

MyHarnessPy 是一个自研 Agent Harness，目标是同时支持 CLI 和 Web，并把模型调用、工具执行、状态管理、权限审批、上下文压缩、Skill 加载、多 Agent 调度等能力统一到一个运行框架里。

它不是普通聊天页面，而是一个“Agent 运行时”。普通聊天系统主要关心消息收发；Harness 还要关心模型是否能调用工具、工具是否安全、状态是否能恢复、长上下文是否会爆、子任务是否能隔离运行，以及前端如何实时展示执行过程。

## 1. 入口层：CLI / Web / REST / WebSocket

入口层负责接收用户输入、展示运行结果，并把请求转发给后端 AgentEngine。入口层本身不直接决定 Agent 的推理逻辑。

对应文件：

- `cli.py`
- `api/rest.py`
- `api/ws.py`
- `static/index.html`

### 1.1 Web UI

Web UI 是当前最完整的交互入口，负责展示：

- 左侧会话列表和子会话树。
- 主消息流、工具调用、工具结果、思考过程。
- 审批面板、question card、运行状态。
- provider、persona、question mode、approval mode 等会话选项。
- rewrite/rerun、重命名、归档、删除等会话操作。

前端不把本地缓存当作真相。切换会话或刷新页面时，会通过 `/sessions/{id}/state` 拉取后端状态，保证后端是单一事实源。

### 1.2 REST API

REST API 是 Web 和外部脚本访问 Harness 的主要入口。它负责把 HTTP 请求转换为对 SessionStore 和 AgentEngine 的调用。

常见接口包括：

- `POST /sessions`：创建会话。
- `POST /sessions/{id}/messages`：发送用户消息。
- `GET /sessions/{id}/state`：读取完整状态快照。
- `POST /sessions/{id}/cancel`：取消运行。
- `POST /sessions/{id}/confirm` / `deny`：处理工具审批。
- `PATCH /sessions/{id}/mode`：切换 question mode。
- `PATCH /sessions/{id}/approval-mode`：切换审批模式。
- `PATCH /sessions/{id}/messages/{message_id}`：重写历史消息并重跑。

REST 层做参数解析、session 查找和状态返回，真正的 Agent 执行仍在 engine 层。

### 1.3 WebSocket

WebSocket 用于实时更新。模型流式输出、状态变化、question、message rewrite、queue 更新等事件都会通过 WebSocket 推送给前端。

这样前端不需要一直轮询，也能及时显示 token、工具调用状态、审批状态和运行结束状态。REST 的 `/state` 仍然保留，主要用于页面刷新、切换会话、断线恢复。

### 1.4 CLI

CLI 复用同一套 `build_engine()`、Provider、ToolRegistry 和 AgentEngine。因此 CLI 与 Web 的核心能力一致，只是交互方式不同。

CLI 适合终端里快速调试 Agent 能力，例如选择 provider、选择 persona、开启 question mode、使用命令系统、连接 MCP 等。

## 2. 会话层：Session、state、tree、rename/pin/archive/delete

会话层负责管理每个 Agent 的生命周期。一个 session 通常对应一个 AgentEngine，也对应一条可持久化的会话记录。

对应文件：

- `api/rest.py`
- `harness/storage/session.py`
- `harness/storage/backends/sqlite.py`
- `harness/storage/backends/memory.py`

### 2.1 Session 与 Engine 映射

后端维护 `_engines: dict[str, AgentEngine]`，把 `session_id` 映射到当前内存中的 engine 实例。还维护 `_engine_meta`，记录 provider、persona、question mode、approval mode、title、display name、parent session 等元数据。

创建会话时，后端会解析 provider/persona/allowed tools，然后调用 `build_engine()` 或 `build_engine_with_mcp()` 创建 engine，并把 session 元数据写入 SessionStore。

如果用户访问一个历史 session，而 engine 已经不在内存里，系统会从 SQLite 读取 messages 和 metadata，再重新构建 engine。这就是刷新页面后还能继续查看历史会话的原因。

### 2.2 状态类型

会话状态分为两类。

运行时状态由 AgentEngine 和 StateMachine 管理：

- `WAITING_INPUT`：等待用户输入。
- `RUNNING`：正在执行主循环。
- `WAITING_CONFIRMATION`：等待工具审批。
- `WAITING_INTERRUPT`：等待用户回答 question。
- `COMPLETED`：当前任务完成。
- `ERROR`：运行出错。

持久化状态由 SessionStore 管理：

- messages。
- title / display name。
- provider / persona。
- question mode / approval mode。
- parent_session_id / spawn_depth。
- pinned / archived / deleted 等会话列表状态。

### 2.3 会话树

子 Agent 会话通过 `parent_session_id` 指向父会话，通过 `spawn_depth` 记录嵌套深度。前端根据这些字段把 session 展示成树，而不是简单平铺。

这个设计已经预留“子 Agent 再创建子 Agent”的情况，所以会话树可以是多层结构。汇报时可以强调：多 Agent 不是只做一次函数调用，而是被纳入了会话管理和 UI 状态管理。

### 2.4 会话管理能力

具有rename、pin、archive、delete、自动命名等能力

自动命名一般根据会话内容生成 title/display name，用于左侧列表展示；rename 则允许用户手动修正标题。

## 3. 主循环层：AgentEngine、ReactLoop、message flow

主循环层是系统的执行核心。它负责把用户输入变成模型调用，把模型 tool call 变成真实工具执行，再把工具结果放回 messages 继续推理。

对应文件：

- `harness/engine/engine.py`
- `harness/engine/loop.py`
- `harness/engine/state_machine.py`
- `harness/types/messages.py`

### 3.1 AgentEngine 负责“状态和入口”

AgentEngine 管理单个会话的运行时对象，包括：

- 当前 messages。
- 当前 EngineState。
- 当前 pending confirmation。
- 当前 pending question。
- 当前 pending command。
- 当前 pending spawn。
- 当前 provider/persona/approval mode/question mode。
- 状态监听器，用于通知 WebSocket 更新前端。

REST 或 CLI 发来的用户输入不会直接调用模型，而是先进入 AgentEngine。AgentEngine 判断当前状态是否合法，再启动或恢复 ReactLoop。

### 3.2 ReactLoop 负责“推理和工具循环”

ReactLoop 是具体 ReAct 流程。每轮执行大致是：

1. 检查取消信号。
2. 在模型调用前做上下文压缩。
3. 从 PromptCache 和 ToolRegistry 取得 system prompt 与工具 schema。
4. 调用 LLM。
5. 如果模型没有 tool call，结束当前任务。
6. 如果模型返回 tool call，先检查是否需要审批。
7. 通过 ToolExecutor 执行工具。
8. 把 tool result 追加回 messages。
9. 进入下一轮，直到完成、出错或达到最大轮数。

这个循环让 Agent 可以多步完成任务，而不是只能“一问一答”。

### 3.3 Message Flow

主流 LLM Provider 对工具消息顺序有严格要求：assistant 发出 tool_call 后，必须紧跟对应 tool result。否则 API 会拒绝请求。

因此系统使用 pending queue 来处理运行中的用户输入。如果工具调用还没闭合，新的用户消息不会直接插入 messages，而是进入 pending_commands，等当前工具链结束后再处理。

这个设计保证了 Agent 可以边运行边接收用户补充，但不会破坏消息协议。


## 4. 模型层：Provider registry、OpenAI-compatible、Anthropic

模型层负责屏蔽不同模型供应商的差异，让主循环只面对统一接口。

对应文件：

- `config.yaml`
- `harness/config.py`
- `harness/llm/registry.py`
- `harness/llm/openai_provider.py`
- `harness/llm/anthropic_provider.py`

### 4.1 Provider 配置

`config.yaml` 的 `providers` 定义可用模型。每个 provider 可以配置 name、model、api_key、base_url 等字段。

`.env` 中的 API key 和 base URL 通过环境变量展开进入配置，例如 `${OPENAI_HUB_API_KEY}`、`${OPENAI_HUB_BASE_URL}`。这样密钥不会写死在仓库里。

`default_provider` 决定新会话默认使用哪个 provider。persona 也可以覆盖 provider，因此不同身份可以绑定不同模型。

### 4.2 Provider Registry

`build_provider(cfg)` 根据 provider 配置创建具体 Provider 实例。当前主要支持：

- OpenAI-compatible Provider。
- Anthropic Provider。

OpenAI Hub、361API、BLTCY 等只要兼容 OpenAI 协议，就可以走 OpenAI-compatible Provider。

### 4.3 统一模型接口

Provider 对外暴露统一方法：

- `chat(messages, tools)`：主推理调用。
- `stream_chat(messages, tools, on_token)`：流式输出。
- `complete(prompt)`：摘要、压缩、自动命名等简单补全场景。

ReactLoop 不需要知道底层服务商是谁，只需要调用统一接口。这也是 Harness 能同时支持多个模型源的关键。

## 5. Prompt 组装层：persona、skills、question mode、tool list

Prompt 组装层负责把系统身份、项目上下文、persona、skill 描述、question mode 规则、工具列表等内容组合成模型真正看到的输入。

对应文件：

- `harness/factory.py`
- `harness/engine/prompt_cache.py`
- `harness/personas.py`
- `harness/skills.py`

### 5.1 Prompt 的组成

Prompt 不是一整块硬编码文本，而是由多个部分拼接：

- 基础系统规则：Agent 应该如何工作。
- 项目上下文：当前项目、文件结构、运行约束。
- persona prompt：当前身份的行为风格和工具限制。
- skill addendum：可用 skill 的名称和描述。
- question mode block：是否允许主动向用户提问。
- tool list：当前允许暴露给模型的工具 schema。
- recovery 指令：工具失败或信息不足时如何继续。

这一层决定模型“以什么身份、知道哪些能力、能不能问用户、能看到哪些工具”。

### 5.2 Persona 如何影响 Prompt

Persona 可以提供 system prompt、provider、allowed_tools 等信息。创建会话或切换 persona 时，系统会把 persona 内容合并进 Prompt，并可能改变模型和工具可见范围。

因此 persona 既是“角色设定”，也是运行权限和模型配置的一部分。

### 5.3 Question Mode 如何影响 Prompt

Question mode 开启时，prompt 会告诉模型可以在必要时使用 `ask_user` 询问用户。关闭时，系统会倾向要求模型自己做合理假设并继续。

这个设计可以让同一套 Agent 在“主动澄清”和“尽量自动完成”之间切换。

### 5.4 PromptCache

PromptCache 缓存 base prompt、persona prompt、mode block 和工具 schema，避免每轮循环都重复扫描和拼接。

当 persona、question mode、工具列表变化时，对应缓存会刷新。这样既能减少运行开销，又能保证 prompt 与当前会话设置一致。

## 6. 工具层：ToolRegistry、ToolExecutor、内置工具、MCP 工具

工具层负责把模型的 tool call 路由成真实动作。

对应文件：

- `harness/tools/registry.py`
- `harness/tools/executor.py`
- `harness/tools/builtin/*`
- `harness/mcp/*`
- `harness/factory.py`

### 6.1 ToolRegistry

ToolRegistry 负责注册工具，并向模型暴露工具 schema。工具 schema 描述工具名、参数结构、说明文本等内容，模型根据这些 schema 决定是否调用工具。

注册阶段会同时考虑内置工具、question mode 工具、skill 工具、多 Agent 工具、MCP 工具，以及 persona 的 allowed_tools。

### 6.2 ToolExecutor

ToolExecutor 接收模型返回的 tool call，解析参数，找到对应工具函数并执行，然后把结果包装成 tool result。

工具执行结果不会直接作为普通 assistant 文本加入，而是作为 tool 消息回到 messages。下一轮模型再根据 tool result 继续推理。

### 6.3 内置工具

当前16个内置工具包括：

- 文件类：`read_file`、`write_file`、`edit_file`、`search`、`glob`、`grep`
- 终端类：`shell`、`powershell`
- 网络类：`web_fetch`、`web_search`
- 思考和计划类：`think`、`todo_write`
- 协作类：`ask_user`
- Skill 类：`use_skill`
- 多 Agent 类：`spawn_agent`、`spawn_agents`

这使模型可以从“只生成文本”变成“读写文件、运行命令、搜索资料、提问用户、拆分子任务”的执行体。

### 6.4 MCP 工具

MCP Server 暴露的工具也会注册进同一个 ToolRegistry。对于模型和 ReactLoop 来说，MCP 工具与内置工具没有本质区别，都是 schema + executor 的形式。

因此 MCP 是工具层的扩展方式，不需要单独作为一层。

## 7. Skill 层：扫描、描述注入、按需全文加载

Skill 层负责把可复用能力做成外部知识模块，让 Agent 在需要时加载专项知识。

对应文件：

- `harness/skills.py`
- `.myharness/skills`
- `.claude/skills`

### 7.1 Skill 扫描

系统会扫描多个目录：

- 当前项目 `.myharness/skills`
- 用户目录 `~/.myharness/skills`
- 当前项目 `.claude/skills`
- 用户目录 `~/.claude/skills`

每个 skill 通常包含名称、描述和正文。扫描阶段主要读取元信息，用于告诉模型有哪些 skill 可用。

### 7.2 描述注入

构建 prompt 时，系统只注入 skill 的名称和 description，而不是把所有 skill 正文一次性塞进上下文。

这样做的原因是：skill 可能很多，如果全部注入，会大量消耗 token，也会让模型注意力变散。

### 7.3 按需全文加载

当模型判断需要某个 skill 时，会调用 `use_skill`。这时系统才读取 skill 全文，并把内容作为工具结果返回给模型。

这种“先看目录，再按需加载正文”的方式类似知识库索引：模型先知道有哪些能力，真正需要时再展开细节。

### 7.4 影响

Skill 层让 Harness 可以在不修改主循环的情况下扩展专项能力。例如前端设计规范、代码审查流程、项目特殊约定，都可以做成 skill。

## 8. Context / Memory 层：messages、SQLite、checkpoint、compression、prompt cache

Context / Memory 层负责保存、压缩和恢复 Agent 的上下文。

对应文件：

- `harness/types/messages.py`
- `harness/engine/compression.py`
- `harness/storage/backends/sqlite.py`
- `harness/storage/checkpoint.py`
- `harness/engine/prompt_cache.py`

### 8.1 Messages 是核心上下文

messages 是当前会话的主要记忆。它包含 user、assistant、tool、system 等消息，也包含 tool call、tool result、压缩标记、溢出引用等元数据。

ReactLoop 每一轮都是基于 messages 调模型。工具结果、用户补充、模型回复也都会回写到 messages。

### 8.2 SQLite 持久化

`config.yaml` 中的 `storage` 决定状态存在哪里。如果使用 SQLite，session 和 messages 会保存到 `harness.db`；如果使用 memory，则只在当前进程内存在。

SQLite 持久化带来的影响是：

- 页面刷新后能恢复会话。
- 服务重启后能查看历史消息。
- 子会话树和会话 metadata 能长期保留。
- 自动命名、归档、置顶等 UI 状态可以保存。

### 8.3 Checkpoint

checkpoint 保存某个时间点的状态，包括 session_id、round_index、EngineState 和 messages。

它现在主要是恢复和调试的基础设施。未来如果要做更完整的回滚、任务恢复、错误现场分析，可以继续扩展 checkpoint 层。

### 8.4 Context Compression

compression 负责解决长上下文问题。当前有两层：

- micro compression：清理旧工具结果的大块正文，保留结构和关键信息。
- auto compression：把较早消息总结成 summary，再保留最近若干消息继续推理。

相关配置在 `config.yaml` 的 `compression` 段。`summary_provider` 决定用哪个模型做摘要，`keep_last_n` 决定保留多少近期上下文。

压缩的影响是双面的：它能省 token、降低成本、防止上下文超限；但如果摘要质量不好，旧任务细节可能丢失。因此压缩模型和压缩策略会影响长期任务稳定性。

### 8.5 PromptCache

PromptCache保存“可复用的上下文构造结果”，例如 base prompt、persona prompt、mode block、工具 schema。

它属于运行时上下文缓存，目的是减少每轮重复构建成本，并保证 prompt 与当前模式一致。

### 8.6 当前 Memory 边界

当前系统已经有会话级持久化和压缩摘要，跨会话长期 MemoryStore。能记住某个 session 的历史，把多个 session 的长期偏好、事实、项目知识沉淀成独立记忆库。

第一版 MemoryStore 已经包含：

- `MemoryEntry`：记录长期记忆内容、scope、tags、来源 session、创建/更新时间。
- `MemoryStore`：提供 `add / get / search / delete` 抽象。
- `InMemoryMemoryStore` 与 `SQLiteMemoryStore`：分别用于测试/临时运行和正式持久化。
- `memory` 工具：模型可以主动写入、查询、列出和删除长期记忆。
- 自动召回：每次运行前，`AgentEngine` 会用最近用户输入搜索 MemoryStore，命中后生成一条临时 system context 注入本轮模型输入。运行结束后这条临时消息会从 `messages` 中移除，不会污染会话历史。
- 管理接口：后端提供 `GET /memory`、`POST /memory`、`DELETE /memory/{entry_id}`，前端后续可以在此基础上增加 Memory 管理面板。

当前边界是：召回仍是简单文本匹配，不是 embedding/vector search；Memory 也还没有置信度、过期时间、来源消息追踪和人工审核流程。因此它已经是独立长期记忆层的第一版，但还不是完整知识库系统。

## 9. 安全层：confirm_tools、approval_mode、tool limits、persona allowed_tools

安全层负责控制 Agent 能不能执行危险动作，以及危险动作是否需要用户审批。

对应文件：

- `config.yaml`
- `harness/config.py`
- `harness/engine/engine.py`
- `harness/personas.py`

### 9.1 confirm_tools

`config.yaml` 中的 `tools.confirm_tools` 决定哪些工具需要审批。当前通常包括：

- `shell`
- `powershell`

当模型调用这些工具时，AgentEngine 会先进入 confirmation gate，不会直接执行。

### 9.2 approval_mode

审批模式由 session 的 `approval_mode` 决定：

- `ask`：每次危险工具调用前询问用户。
- `auto`：自动批准，但仍保留受控工具调用记录。
- `full`：绕过 confirm_tools gate，相当于当前 session 全权限运行。

所以“哪个主智能体是全权限”不是固定由某个 persona 决定，而是看当前 session 的 `approval_mode` 是否为 `full`。

### 9.3 persona allowed_tools

persona 可以提供 `allowed_tools`，限制该身份能看到哪些工具。模型看不到的工具就不容易调用，因此这是 prompt 层和工具层共同实现的权限收缩。

例如一个只负责分析的 persona 可以只允许 read/search，不允许 write/shell。

### 9.4 tool limits

tool limits 用于限制工具运行边界，例如超时、输出大小等。它的作用是避免工具调用失控、输出过大或长时间阻塞。

安全层的核心取舍是：权限越宽，自动化能力越强；权限越窄，安全性越高，但人工确认和限制也更多。

## 10. 人机协作层：ask_user、question card、WAITING_INTERRUPT

人机协作层负责让 Agent 在不确定时结构化地向用户提问，而不是随意中断或编造答案。

对应文件：

- `harness/tools/builtin/ask_user.py`
- `harness/types/questions.py`
- `harness/engine/engine.py`
- `api/rest.py`
- `api/ws.py`
- `static/index.html`

### 10.1 question mode

当 question mode 开启时，系统会注册 `ask_user` 工具，并在 prompt 中告诉模型可以向用户提问。

当 question mode 关闭时，prompt 会倾向要求模型做合理假设并继续，避免频繁打断用户。
模型调用 `ask_user` 后，系统会创建结构化 `QuestionRequest`。这个请求包含问题文本、选项、是否可跳过等信息。

前端收到 WebSocket 事件后，把它显示为 question card。用户回答后，答案通过 REST/WS 返回给 AgentEngine。

### 10.2 WAITING_INTERRUPT

等待用户回答时，AgentEngine 进入 `WAITING_INTERRUPT`。这表示当前模型流程暂停，但消息流仍保持合法状态。

用户回答后，engine 把答案送回对应等待点，再恢复 RUNNING。这样人类反馈成为主循环的一部分，而不是破坏消息顺序的临时插队。

## 11. 多 Agent 层：spawn_agent、spawn_agents、parent_session_id、pending_spawns

多 Agent 层负责把复杂任务拆给子 Agent，并把子 Agent 的结果汇总回主会话。

对应文件：

- `harness/tools/builtin/spawn_agent.py`
- `harness/factory.py`
- `api/rest.py`
- `static/index.html`

### 11.1 创建子 Agent

主 Agent 可以调用：

- `spawn_agent`：创建一个子 Agent。
- `spawn_agents`：批量创建多个子 Agent。

每个子 Agent 都有独立 session、messages、provider、persona、title 和状态。它不是普通函数调用，而是一个完整的 Agent 会话。

### 11.2 父子关系

子 Agent 通过 `parent_session_id` 连接到父会话，通过 `spawn_depth` 控制嵌套深度。

前端根据这些字段显示树形会话。设计上允许子 Agent 继续创建子 Agent，因此适合表达复杂任务分解。

### 11.3 pending_spawns

`pending_spawns` 用于记录父 Agent 正在等待哪些子任务。父 Agent 可以把探索性工作交给子 Agent，让自己的上下文保持干净。

子 Agent 完成后，结果回到父 Agent，父 Agent 再做整合和决策。


## 12. 运行时增强层：pending_commands、rewrite/rerun、events、WebSocket、自动命名

运行时增强层不是单独的核心执行链路，但它让 Harness 更接近真实可用的产品。

### 12.1 pending_commands

pending_commands 用于处理运行中的用户输入。如果 Agent 正在执行工具，新的用户输入不会直接插入 messages，而是进入队列。

当前工具链完成后，系统再处理队列里的用户输入。这保证了 tool_call 和 tool_result 的顺序合法。

### 12.2 rewrite / rerun

rewrite/rerun 允许用户修改历史消息，并从某个点重新运行。

这对调试 Agent 很重要：用户可以修正一个错误提示词，然后重跑后续流程，而不是只能开新会话。

### 12.3 events 与 WebSocket 观测

events 记录或推送运行时事件，例如 state transition、tool call、compression、question、rewrite 等。

WebSocket 把这些事件实时推给前端，让 UI 能显示 token 流、状态变化、审批卡片、问题卡片和队列变化。

### 12.4 自动命名

自动命名根据会话内容生成 title/display name，让左侧会话列表更容易阅读。

它属于会话体验增强，不改变主循环逻辑，但对 Web 端长期使用很重要。

### 12.5 命令系统

命令系统可以提供 show-state、summary 等内部能力。它适合 CLI 和 Web 中的快速操作，也可以作为调试入口。

## 13. 其他功能

这一章放一些已经实现、但不适合单独作为架构层的功能。它们通常横跨前端、REST、AgentEngine 和存储层，属于让系统真正可用的细节能力。

### 13.1 会话内自由切换审批模式

系统支持在同一个 session 内切换 `approval_mode`，不需要重新创建会话。

对应接口是 `PATCH /sessions/{id}/approval-mode`。前端顶部的权限 pill 可以在 `ask`、`auto`、`full` 之间循环切换；后端会调用 `engine.set_approval_mode()` 更新当前 AgentEngine，并把新模式写入 session metadata。

三个模式的含义是：

- `ask`：危险工具调用前弹出审批。
- `auto`：危险工具自动批准，但仍保留受控工具记录。
- `full`：绕过 confirm_tools gate，当前 session 直接执行。

这个功能的意义是：同一个主智能体可以先保守运行，确认可信后临时切到全权限；也可以在风险较高的任务中切回手动审批。


### 13.2 会话内 Persona 切换

系统支持在会话中途切换 persona。切换后，后端会更新 engine 的 persona prompt，并同步更新 session metadata。

这个能力适合把同一个会话从“规划者”切到“实现者”或“审查者”，不必重新开一个会话。persona 还可以携带 provider 和 allowed_tools，因此它不仅改变语气，也会影响模型选择和工具可见范围。

### 13.3 自动命名和展示名

系统会根据会话内容生成 title 或 display name，用于左侧会话列表和子会话树展示。生成失败时会回退到用户消息的前几个字符或默认标题。

自动命名不影响推理逻辑，但对 Web 端长期使用很关键，因为用户可以从标题快速识别每个主会话和子会话的任务。

### 13.4 前端会话树与标题展示

左侧面板现在以会话为中心展示，不再把 skill/persona 管理入口堆在侧边栏里。主会话和子会话按树形排列，并优先显示手动命名、自动生成 title 或 display name。

这个改动让 UI 更接近真实任务工作台：左侧负责导航任务树，配置和 persona/skill 管理放到更合适的配置入口中。

### 13.5 运行中输入排队

当 Agent 正在运行时，用户仍然可以继续输入。系统不会把新输入直接插进 messages 中间，而是放入 pending_commands，等待当前工具调用链闭合后再处理。

这个细节解决了一个很重要的问题：LLM 工具调用要求 assistant tool_call 后面必须紧跟 tool result。如果用户消息插在中间，下一次模型请求可能直接报错。

### 13.6 消息重写和从中间重跑

系统支持修改历史消息并从该点重新运行。这让用户可以修正某次提示词或任务描述，然后让后续结果重新生成。

这个功能适合调试 Agent 行为，也适合课堂汇报时展示“同一个任务，修改条件后如何重新执行”。

### 13.7 统一任务视图 TaskRecord / TaskStatus

系统新增了轻量 `TaskRecord / TaskStatus`，用于把几个原本分散的运行时概念统一展示：

- `plan_item`：来自 `todo_write` / `PlanStore` 的计划步骤。
- `queued_command`：运行中继续输入后进入 pending queue 的用户命令。
- `subagent`：正在运行的 pending sub-agent。

它们会被汇总到 `/sessions/{id}/state` 的 `tasks` 字段。这样前端后续可以只消费一个任务列表，就能展示“当前计划、排队输入、子智能体执行”三类状态。

当前 `TaskRecord` 是快照层，不是独立持久化任务表。也就是说，它先解决“统一展示和汇报”的问题；后续如果要做跨 session 工作图、任务历史和完成率统计，可以再升级成持久 `TaskStore`。

### 13.8 Shell 的 Python fallback

shell 工具中有 Python fallback 逻辑，用于在某些环境下找到可用 Python 解释器。这和当前项目里 Anaconda Python 的使用有关，可以降低 Windows 环境下命令执行失败的概率。

### 13.9 AgentProfile spawn 权限

Persona 已经升级为第一版 `AgentProfile`，除了 system prompt、provider、allowed_tools 之外，还可以配置：

- `can_spawn`：当前 agent 是否允许创建子 agent。
- `spawn_allowlist`：如果允许创建子 agent，只能创建哪些指定 agent。

`spawn_agent` 和 `spawn_agents` 在真正创建子会话前会读取父 agent profile 并检查权限。没有配置这些字段的旧 persona 默认保持兼容，也就是允许 spawn；只有显式关闭或设置 allowlist 时才收紧。

这个能力让“主智能体”和“子智能体”的边界更清楚。例如 planner 可以允许 spawn reviewer，但 docs-writer 可以禁止 spawn，避免普通写作任务无限拆分。
