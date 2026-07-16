# Atelier

[English](README.md) | [简体中文](README.zh-CN.md)

Atelier 是我们实验室独立开发的轻量级智能体脚手架，目标是为专业设计场景构建可扩展的设计智能体运行底座。它兼顾 Web UI 和 CLI，提供未来设计工作流需要的基础能力：项目会话、工具执行、任务规划、记忆、技能、多智能体、人机审批和实时执行过程可视化。

当前仓库重点完成的是通用 harness 层，具体的设计领域工具和设计工作流会在后续继续加入。换句话说，它不是简单的大模型聊天壳，而是面向设计智能体的运行时基础设施：智能体可以推理、行动、澄清需求、调用工具、持久化上下文、从错误中恢复，并通过子智能体协作推进复杂任务。

## 核心特性

- **设计智能体脚手架**：为后续专业设计流程提供轻量基础，包括调研、规划、迭代、评审和面向产物的工具调用。
- **Web 与 CLI 双入口**：既可以用浏览器工作台，也可以直接运行 `cli.py`。
- **OpenAI-compatible 与 Anthropic 模型提供商**：通过 `config.yaml` 和环境变量配置模型。
- **工具注册与执行系统**：支持文件操作、Shell / PowerShell、网页搜索、网页抓取、思考、记忆、计划、后台任务和子智能体。
- **审批模式**：危险工具可请求人工确认，也可按会话切换自动执行或全权限模式。
- **会话持久化**：使用 SQLite 保存会话、元数据、checkpoint、可见计划和 memory。
- **实时执行过程**：通过 REST + WebSocket 展示消息、工具调用、工具结果、计划更新、审批和恢复事件。
- **Skill 与 Agent Profile**：从 `.myharness/` 扫描项目内智能体、技能和命令，并注入到 prompt 上下文。
- **多智能体支持**：主会话可以生成子会话，并保留父子关系。
- **上下文管理**：支持自动压缩和 prompt cache，让长会话可以继续运行。

## 这个 Harness 提供什么

Atelier 可以理解为一组可复用的智能体运行时层，后续可以在这些层之上构建设计场景中的专业智能体产品。

### 入口层

项目支持三类入口：

- **Web UI**：由 `static/index.html` 提供，后端使用 FastAPI。
- **CLI**：通过 `cli.py` 直接本地交互。
- **REST / WebSocket API**：由 `api/rest.py` 和 `api/ws.py` 提供，便于接入其他界面。

这样设计可以让智能体运行时不绑定某一个前端。后续如果要做真正的设计工作台，可以复用同一个后端，再扩展新的界面。

### 会话层

Session 是一次工作的持久化单位。每个 session 保存消息、元数据、标题、当前智能体、provider、审批模式、提问模式、计划状态，以及子智能体的父子关系。

Web UI 可以列出、恢复、重命名、置顶、归档和删除会话。后端会从 SQLite 恢复会话状态，因此长程设计任务可以跨浏览器刷新或服务重启继续。

### 智能体运行层

核心运行时是 ReAct 风格循环：

```text
组装 prompt -> 调用模型 -> 解析工具调用 -> 执行工具 -> 保存结果 -> 继续推理或返回回答
```

它不是单轮聊天，而是为长任务设计的执行循环。工具执行后可以继续推理，中途可以展示进度，也可以等待审批、主动提问或从部分中断状态恢复。

### 模型层

Provider registry 支持 OpenAI-compatible chat-completion 接口和 Anthropic 风格接口。模型配置写在 `config.yaml`，密钥保存在 `.env`。

这样可以在不同模型供应商、本地代理和中转服务之间切换，而不需要改智能体主循环。

### Prompt 与智能体配置层

智能体配置位于 `.myharness/personas/`。每个 profile 可以定义角色、系统提示词、默认 provider、默认审批模式和可用工具。

当前已有 builder、planner、reviewer、debugger、researcher、docs-writer 等通用角色。后续可以用同样格式添加更设计化的角色，例如 design-researcher、layout-critic、prototype-builder、visual-spec-writer。

### 工具层

工具由中心 ToolRegistry 注册，并由 ToolExecutor 执行。内置工具覆盖文件编辑、搜索、命令执行、网页访问、记忆、计划、后台任务和子智能体创建。

MCP 工具也可以桥接进同一个注册系统，但 harness 保留了自己的核心工具，因此本地工作流不会完全依赖外部 MCP 行为。

### Skill 层

Skill 是可复用的流程知识。系统会扫描项目 skill，把短描述注入 prompt；只有当智能体显式调用 skill 工具时，才加载完整 skill 内容。

这种两阶段加载可以避免 prompt 一开始就被大量资料占满，同时保留按需调用专业流程的能力。后续设计方法、评审标准、调研流程都可以沉淀为 skill。

### Context 与 Memory 层

系统保存对话消息、持久化 memory、可见 plan、checkpoint 和压缩摘要。上下文变长时会触发压缩：保留最近消息，同时总结更早的上下文。

在设计场景中，这一层可以用来保留项目决策、用户偏好、约束条件、评审意见和跨会话可复用的信息。

### 安全与审批层

Shell、PowerShell 等危险工具可以要求人工确认。审批模式可以按 session 切换，智能体 profile 也可以限制可用工具。

这对设计智能体很重要，因为后续它可能会编辑文件、生成产物、运行命令或调用外部服务。

### 人机协作层

智能体可以用结构化问题向用户澄清需求，而不是在需求不明确时直接猜测。用户回答后，引擎会从原任务继续运行。

这适合“先问清楚设计目标，再做计划或实现”的工作流。

### 多智能体层

运行时支持通过 `spawn_agent` 和 `spawn_agents` 创建子智能体。子智能体拥有独立上下文，同时保留和父会话的关系。

这让设计任务可以拆成调研、规划、实现、评审、文档等多个角色协作完成。

### 运行时可视化层

Web UI 通过 WebSocket 接收运行事件，可以展示模型轮次、工具调用、工具结果、计划更新、审批请求、恢复提示和中间思考/工具轨迹。

可观察性是这个项目的重要目标：用户应该能看见设计智能体正在做什么，而不是只能等待最后结果。

## 仓库结构

```text
.
|-- api/                    # FastAPI REST 与 WebSocket 服务
|-- harness/                # 智能体运行时、工具、存储、模型提供商
|   |-- engine/             # 主循环、状态机、压缩、prompt cache
|   |-- tools/              # 内置工具与执行层
|   |-- storage/            # SQLite / memory 后端、plan 与 memory store
|   |-- llm/                # 模型提供商抽象与实现
|   |-- mcp/                # MCP bridge 与 transport
|   `-- commands/           # 内置命令与项目命令系统
|-- static/                 # 浏览器前端
|-- .myharness/             # 项目智能体、技能、命令、transcript
|-- tests/                  # 单元测试与集成测试
|-- cli.py                  # CLI 入口
|-- config.yaml             # 运行时配置
`-- pyproject.toml          # Python 包配置
```

## 快速开始

### 1. 安装

需要 Python 3.11 或更新版本。

```bash
pip install -e ".[dev]"
```

### 2. 配置环境变量

从 `.env.example` 创建 `.env`，然后填写你需要使用的模型提供商。

默认 OpenAI-compatible 通路示例：

```env
OPENAI_HUB_API_KEY=your-api-key
OPENAI_HUB_BASE_URL=https://api.openai-hub.com/v1
OPENAI_HUB_MODEL=gpt-4o
HARNESS_DEFAULT_PROVIDER=openai-hub
```

如果需要真实网页搜索，推荐配置 Serper：

```env
SERPER_API_KEY=your-serper-key
```

如果没有搜索 key，`web_search` 会降级到能力有限的 DuckDuckGo instant-answer fallback。

如果要使用设计图片生成和图片编辑工具，请配置 `image_generate` 与 `image_edit` 使用的图片接口：

```env
DESIGN_IMAGE_API_KEY=your-image-api-key
DESIGN_IMAGE_BASE_URL=https://api.openai-hub.com/v1
DESIGN_IMAGE_MODEL=gpt-image-2
DESIGN_IMAGE_ENDPOINT=https://api.openai-hub.com/v1/images/generations
DESIGN_IMAGE_EDIT_ENDPOINT=https://api.openai-hub.com/v1/images/edits
```

如果没有单独设置 `DESIGN_IMAGE_API_KEY` 或 `DESIGN_IMAGE_BASE_URL`，图片工具会回退使用 `OPENAI_HUB_API_KEY` 和 `OPENAI_HUB_BASE_URL`。也可以设置 `DESIGN_IMAGE_DEFAULT_SIZE`，例如 `1024x1024`。

### 3. 启动 Web UI

```bash
uvicorn api.rest:app --port 8000
```

浏览器打开：

```text
http://localhost:8000
```

执行长任务时不建议加 `--reload`。智能体写文件可能触发服务重启，导致当前会话被中断。

### 4. 使用 CLI

```bash
python cli.py
python cli.py --persona builder
python cli.py --provider openai-hub
```

## 配置说明

主要配置文件是 `config.yaml`。

常用配置项：

- `default_provider`：新会话默认使用的模型提供商。
- `providers`：OpenAI-compatible 和 Anthropic provider 定义。
- `engine.max_rounds`：一次任务最多执行多少轮模型循环。
- `compression`：上下文窗口、压缩触发比例、保留最近消息数量、摘要模型。
- `storage`：SQLite 或内存存储后端。
- `tools.enabled`：全局启用的工具列表。
- `tools.confirm_tools`：需要人工确认的工具。
- `tools.limits`：每个工具的输出限制和执行限制。
- `mcp_servers`：可选 MCP 服务配置。

`config.yaml` 支持从环境变量展开配置，因此 API Key 等敏感信息应该放在 `.env`，不要提交到仓库。

## 内置工具

常见内置工具：

| 工具 | 用途 |
| --- | --- |
| `read_file`, `write_file`, `edit_file`, `create_directory`, `list_dir` | 文件系统操作 |
| `write_json` | 结构化 JSON 文件写入 |
| `grep`, `glob`, `search` | 代码和文本搜索 |
| `shell`, `powershell` | 本地命令执行 |
| `web_search`, `web_fetch` | 网页搜索与网页读取 |
| `image_generate`, `image_edit` | 设计图片生成与编辑 |
| `todo_write` | 创建和更新可见计划 |
| `memory` | 持久化记忆读写 |
| `think` | 显式思考过程，前端可展示为执行轨迹 |
| `background_task` | 后台长任务 |
| `spawn_agent`, `spawn_agents` | 创建子智能体 |
| `use_skill` | 按需加载完整 skill 内容 |

工具通过 harness 的 ToolRegistry 注册，并以可调用函数的形式暴露给模型。MCP 工具也可以桥接到同一个工具注册系统里。

## Agent、Skill 与 Command

项目本地行为主要放在 `.myharness/` 下。

```text
.myharness/
├── personas/       # builder、planner、reviewer 等智能体配置
├── skills/         # 可复用技能描述和完整技能内容
├── commands/       # 项目命令
└── transcripts/    # 运行时 transcript
```

Agent profile 会控制系统提示词、默认 provider、默认审批模式和工具权限。Skill 采用两阶段加载：短描述会被注入 prompt；完整内容只有在智能体调用 skill 工具时才加载，避免上下文被过早占满。

## 运行时流程

每个 session 的核心流程大致是：

```text
用户输入
  -> 组装 prompt
  -> 注入 memory / plan / skill 上下文
  -> 必要时压缩上下文
  -> 调用模型
  -> 执行工具
  -> 持久化工具结果
  -> 进入下一轮模型推理或返回最终回复
```

Engine 会保存消息和会话元数据，发出运行时事件，并通过 WebSocket 推送给前端。因此用户可以看到中间执行过程，而不是只能等待最终回答。

## 安全与权限

Atelier 包含几层安全控制：

- 危险工具可以要求用户确认。
- 审批模式可以按会话切换。
- Agent profile 可以限制可用工具。
- 工具输出有上限，避免上下文溢出。
- Shell 执行尽量使用明确参数，降低命令注入风险。
- 状态切换由状态机检查，避免非法运行状态。

它仍然是本地研究型 harness。在暴露给不可信用户或运行在敏感机器之前，请先审查 `config.yaml`。

## REST 与 WebSocket API

Web UI 通过 FastAPI 后端通信。

常用接口：

| 接口 | 用途 |
| --- | --- |
| `POST /sessions` | 创建或恢复会话 |
| `POST /sessions/{id}/messages` | 发送用户消息 |
| `GET /sessions/{id}/state` | 获取完整会话快照 |
| `POST /sessions/{id}/continue` | 从可恢复状态继续 |
| `POST /sessions/{id}/cancel` | 取消运行中的会话 |
| `POST /sessions/{id}/confirm` / `deny` | 处理审批请求 |
| `PATCH /sessions/{id}/approval-mode` | 切换审批模式 |
| `GET /config/agents` | 列出智能体配置 |
| `GET /memory` / `POST /memory` | 管理 memory |
| `GET /commands` | 列出项目命令 |
| `WS /ws/{session_id}` | 推送运行时事件 |

## 相关文档

- [网页版开发者文档](developer-docs/index.html)

## 开发

运行测试：

```bash
pytest
```

常用定向测试：

```bash
pytest tests/test_engine.py
pytest tests/test_tools.py
pytest tests/test_storage.py
pytest tests/test_streaming.py
```

## 项目状态

这是一个仍在迭代的学术 / 研究型 harness，也是面向专业设计智能体脚手架的基础版本。核心运行时能力已经实现，但设计领域工具、产物工作流、权限加固、UI 体验、memory 管理和生产部署仍需要继续完善。

## License

Atelier 使用 [MIT License](LICENSE) 开源。
