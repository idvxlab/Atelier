# Atelier

[English](README.md) | [简体中文](README.zh-CN.md)

Atelier 是一个面向专业设计智能体的轻量级 Agent Harness。它不是单纯的大模型聊天页面，而是一套可控制、可观察、可审批、可持久化、可扩展的智能体运行底座：智能体可以在同一个会话中理解需求、规划任务、调用工具、保存上下文、请求人工确认、生成子智能体，并通过 WebSocket 把执行过程实时呈现给用户。

当前版本聚焦通用运行时能力，适合作为设计智能体、研究型工作台、本地自动化助手，以及需要稳定执行、工具治理、持久化会话和可观察长任务的多智能体系统基础。

![Atelier 运行时架构](docs/assets/atelier-runtime-v4-clean-fresh-zh.svg)

## 核心亮点

- **Web、CLI 与 API 多入口**：既可以使用浏览器工作台，也可以运行本地交互式 CLI，或通过 REST / WebSocket API 接入自定义前端。
- **长任务智能体运行时**：采用 ReAct 风格循环，支持多轮模型调用、工具执行、中途取消、状态恢复和最终回复生成。
- **模型 Provider 抽象**：支持 OpenAI-compatible 与 Anthropic 风格接口，模型、Base URL 和密钥都通过 `config.yaml` 与环境变量配置。
- **可扩展工具系统**：内置文件操作、搜索、Shell / PowerShell、网页搜索、网页抓取、图片生成/编辑、计划、记忆、后台任务和子智能体创建。
- **会话持久化**：使用 SQLite 保存消息、元数据、计划、记忆、checkpoint 和父子会话关系。
- **审批与权限控制**：高风险工具可要求人工确认，persona 也可以限制会话可用工具。
- **Personas、Skills 与 Commands**：角色、流程知识和项目命令从 `.myharness/` 加载，便于复用和管理。
- **上下文管理**：prompt cache 与自动压缩让长会话在上下文增长后仍能继续运行。
- **多智能体协作**：父会话可以创建子智能体，用于调研、规划、实现、评审、文档等专业角色分工。
- **运行时可观察性**：前端可以展示模型轮次、工具调用、工具结果、计划变化、审批请求、恢复事件和流式状态更新。

## 适用场景

Atelier 面向需要“可执行智能体”而不只是“单轮聊天助手”的团队与研究者：

- 构建设计调研、视觉产物生成、方案评审、原型迭代和面向产物工作流的专业设计智能体。
- 搭建可本地运行的 AI 工作台，让智能体在可控权限下读取和修改项目文件。
- 研究多智能体协作、可中断执行、人机审批、上下文压缩和可恢复长任务。
- 将现有模型网关、MCP 服务、内部工具或设计领域服务接入统一工具注册体系。
- 在 Web 工作台、CLI 和自定义产品界面之间复用同一套后端智能体能力。

## ??????

??????????????????????? [`example_outputs/runs/`](example_outputs/runs/)????????????????????? `outputs/` ?????????????????? `final/` ????????????????????????????????

????????????? PNG ???README ???????????????????????????

### ????????????

??????????????????????????????????????????

[??????](example_outputs/runs/jingju-guochao-merch/final/00-index.html) ? [??????](example_outputs/runs/jingju-guochao-merch/final/artifacts/00-gallery.html)

| ???? | ???? | ???? |
| --- | --- | --- |
| <img src="example_outputs/runs/jingju-guochao-merch/final/artifacts/generated-images/01-product-overview.png" width="220" alt="????????"> | <img src="example_outputs/runs/jingju-guochao-merch/final/artifacts/generated-images/07-packaging-application.png" width="220" alt="????????"> | <img src="example_outputs/runs/jingju-guochao-merch/final/artifacts/generated-images/10-series-overview.png" width="220" alt="????????"> |
| ???? | ???? | ???? |
| <img src="example_outputs/runs/jingju-guochao-merch/final/artifacts/generated-images/05-detail-closeup.png" width="220" alt="????????"> | <img src="example_outputs/runs/jingju-guochao-merch/final/artifacts/generated-images/06-lifestyle-use.png" width="220" alt="????????"> | <img src="example_outputs/runs/jingju-guochao-merch/final/artifacts/design-spec/cultural-palette.png" width="220" alt="????????"> |

### ???????? IDVX ???

??????????????????????????????????????????????

[??????](example_outputs/runs/tongji-idvx-lab-merch/final/00-index.html) ? [??????](example_outputs/runs/tongji-idvx-lab-merch/final/artifacts/00-gallery.html)

| ????? | ????? | ????? |
| --- | --- | --- |
| <img src="example_outputs/runs/tongji-idvx-lab-merch/final/artifacts/generated-images/01-tote-hero-front.png" width="220" alt="?? IDVX ?????"> | <img src="example_outputs/runs/tongji-idvx-lab-merch/final/artifacts/generated-images/02-tote-detail-strap.png" width="220" alt="?? IDVX ?????"> | <img src="example_outputs/runs/tongji-idvx-lab-merch/final/artifacts/generated-images/03-notebook-cover.png" width="220" alt="?? IDVX ?????"> |
| ????? | ???? | ???? |
| <img src="example_outputs/runs/tongji-idvx-lab-merch/final/artifacts/generated-images/04-notebook-open-spread.png" width="220" alt="?? IDVX ?????"> | <img src="example_outputs/runs/tongji-idvx-lab-merch/final/artifacts/generated-images/05-badge-set-board.png" width="220" alt="?? IDVX ????"> | <img src="example_outputs/runs/tongji-idvx-lab-merch/final/artifacts/generated-images/08-campus-application-scene.png" width="220" alt="?? IDVX ??????"> |

### ??????????? AI ????

???????????????????????????????????CMF ??????

[??????](example_outputs/runs/elderly-ai-companion-device/final/00-index.html) ? [??????](example_outputs/runs/elderly-ai-companion-device/final/artifacts/00-gallery.html)

| ????? | ??? | ???? |
| --- | --- | --- |
| <img src="example_outputs/runs/elderly-ai-companion-device/final/artifacts/generated-images/01-hero-render.png" width="220" alt="AI ?????????"> | <img src="example_outputs/runs/elderly-ai-companion-device/final/artifacts/generated-images/02-three-view.png" width="220" alt="AI ???????"> | <img src="example_outputs/runs/elderly-ai-companion-device/final/artifacts/generated-images/03-usage-scene-bedroom.png" width="220" alt="AI ??????????"> |
| ???? | CMF ? | ???? |
| <img src="example_outputs/runs/elderly-ai-companion-device/final/artifacts/generated-images/05-detail-interaction.png" width="220" alt="AI ????????"> | <img src="example_outputs/runs/elderly-ai-companion-device/final/artifacts/generated-images/06-cmf-board.png" width="220" alt="AI ???? CMF ???"> | <img src="example_outputs/runs/elderly-ai-companion-device/final/artifacts/generated-images/07-form-language.png" width="220" alt="AI ?????????"> |

### ?????????????

??????????????????????????????????????????????

[??????](example_outputs/runs/zhujiajiao-visitor-center-space/final/00-index.html) ? [??????](example_outputs/runs/zhujiajiao-visitor-center-space/final/artifacts/00-gallery.html)

| ???? | ????? | ???? |
| --- | --- | --- |
| <img src="example_outputs/runs/zhujiajiao-visitor-center-space/final/artifacts/generated-images/01-site-context-relation.png" width="220" alt="???????????"> | <img src="example_outputs/runs/zhujiajiao-visitor-center-space/final/artifacts/generated-images/02-master-plan-zoning.png" width="220" alt="????????????"> | <img src="example_outputs/runs/zhujiajiao-visitor-center-space/final/artifacts/generated-images/03-circulation-flow.png" width="220" alt="???????????"> |
| ???? | ???? | ????? |
| <img src="example_outputs/runs/zhujiajiao-visitor-center-space/final/artifacts/generated-images/06-hero-entry-hall.png" width="220" alt="???????????"> | <img src="example_outputs/runs/zhujiajiao-visitor-center-space/final/artifacts/generated-images/10-facade-elevation.png" width="220" alt="???????????"> | <img src="example_outputs/runs/zhujiajiao-visitor-center-space/final/artifacts/generated-images/11-material-light-board.png" width="220" alt="?????????????"> |

### ??????IEEE VIS 2026 ????

???????????????????????????????????????????

[??????](example_outputs/runs/ieee-vis-2026-promo/final/00-index.html) ? [??????](example_outputs/runs/ieee-vis-2026-promo/final/artifacts/00-gallery.html)

| ??? | ??? | ???? |
| --- | --- | --- |
| <img src="example_outputs/runs/ieee-vis-2026-promo/final/artifacts/generated-images/01-main-poster.png" width="220" alt="IEEE VIS 2026 ???"> | <img src="example_outputs/runs/ieee-vis-2026-promo/final/artifacts/generated-images/02-key-visual.png" width="220" alt="IEEE VIS 2026 ???"> | <img src="example_outputs/runs/ieee-vis-2026-promo/final/artifacts/generated-images/03-typography-hierarchy-board.png" width="220" alt="IEEE VIS 2026 ?????"> |
| ???? | ???? | ???? |
| <img src="example_outputs/runs/ieee-vis-2026-promo/final/artifacts/generated-images/05-social-twitter-post.png" width="220" alt="IEEE VIS 2026 ???????"> | <img src="example_outputs/runs/ieee-vis-2026-promo/final/artifacts/generated-images/10-badge-lanyard.png" width="220" alt="IEEE VIS 2026 ??????"> | <img src="example_outputs/runs/ieee-vis-2026-promo/final/artifacts/generated-images/11-ppt-template.png" width="220" alt="IEEE VIS 2026 ????"> |

### ??????????????

???????????????????????????? mockup ? moodboard?

[??????](example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/00-index.html) ? [??????](example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/artifacts/00-gallery.html)

| ?????? | ???? | ???? |
| --- | --- | --- |
| <img src="example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/01-logo-application-poster.png" width="220" alt="????????????"> | <img src="example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/02-campaign-poster-zh.png" width="220" alt="??????????"> | <img src="example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/03-campaign-poster-en.png" width="220" alt="??????????"> |
| ???? | ?? mockup | Moodboard |
| <img src="example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/04-social-card-announce.png" width="220" alt="??????????"> | <img src="example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/07-merch-mockup.png" width="220" alt="???????? mockup"> | <img src="example_outputs/runs/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/09-moodboard.png" width="220" alt="?????? moodboard"> |

## 产品架构

Atelier 可以分为五个运行时层级：

| 层级 | 职责 |
| --- | --- |
| 入口层 | Web UI、CLI、REST API、WebSocket 流式事件 |
| 会话层 | 会话创建、恢复、改名、置顶/归档、父子关系、运行状态 |
| 智能体运行层 | prompt 组装、模型调用、工具调用、审批门禁、状态机、取消和恢复 |
| 扩展层 | tools、skills、personas、commands、MCP bridge |
| 存储层 | SQLite 或内存后端，保存消息、计划、记忆和会话元数据 |

## 运行流程

一次典型任务的执行过程如下：

1. 用户从 Web UI、CLI 或 API 发送请求。
2. 引擎组装系统提示、persona、skill 描述、memory、plan 状态和历史消息。
3. 模型决定直接回复，或请求一个/多个工具调用。
4. 工具调用在执行前经过当前审批模式处理。
5. 工具结果写回会话，并通过 WebSocket 实时推送给前端。
6. 如果还需要继续工作，引擎进入下一轮模型调用；否则返回最终回答。

## 仓库结构

```text
.
|-- api/                    # FastAPI REST 与 WebSocket 服务
|-- harness/                # Agent runtime、工具、存储、LLM providers
|   |-- engine/             # 主循环、状态机、压缩、prompt cache
|   |-- tools/              # 内置工具和执行层
|   |-- storage/            # SQLite 与内存存储后端
|   |-- llm/                # Provider 抽象和实现
|   |-- mcp/                # MCP bridge 与 transports
|   `-- commands/           # 内置命令与项目命令系统
|-- static/                 # 浏览器前端
|-- .myharness/             # Personas、skills、commands、transcripts
|-- tests/                  # 单元测试和集成测试
|-- cli.py                  # 交互式 CLI 入口
|-- config.yaml             # 运行时配置
|-- pyproject.toml          # Python 包配置
`-- README.md
```

## 环境要求

- Python 3.11 或更新版本
- 一个可用的模型服务：
  - OpenAI-compatible Chat Completions API，或
  - Anthropic-compatible Provider
- 可选：Serper 或 Brave Search API Key，用于完整网页搜索
- 可选：图片生成/编辑接口，用于 `image_generate` 和 `image_edit`

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 配置环境变量

创建本地环境文件：

```bash
cp .env.example .env
```

填写你要使用的模型服务。默认 OpenAI-compatible 通路示例：

```env
OPENAI_HUB_API_KEY=your-api-key
OPENAI_HUB_BASE_URL=https://your-openai-compatible-endpoint/v1
OPENAI_HUB_MODEL=gpt-4o
HARNESS_DEFAULT_PROVIDER=openai-hub
```

如需完整网页搜索：

```env
SERPER_API_KEY=your-serper-key
BRAVE_SEARCH_API_KEY=your-brave-key
```

如需图片生成与编辑：

```env
DESIGN_IMAGE_API_KEY=your-image-api-key
DESIGN_IMAGE_BASE_URL=https://your-image-endpoint/v1
DESIGN_IMAGE_MODEL=gpt-image-2
DESIGN_IMAGE_ENDPOINT=https://your-image-endpoint/v1/images/generations
DESIGN_IMAGE_EDIT_ENDPOINT=https://your-image-endpoint/v1/images/edits
DESIGN_IMAGE_DEFAULT_SIZE=1024x1024
```

### 3. 启动 Web Workspace

```bash
uvicorn api.rest:app --port 8000
```

浏览器打开：

```text
http://localhost:8000
```

长任务或会写文件的智能体任务不建议使用 `--reload`。文件变化可能触发服务重启，从而中断当前会话。

### 4. 使用 CLI

```bash
python cli.py
python cli.py --persona builder
python cli.py --provider openai-hub
python cli.py --question-mode question
```

CLI 常用命令：

| 命令 | 说明 |
| --- | --- |
| `/exit` 或 `/quit` | 退出 CLI |
| `/reset` | 开启新会话 |
| `/tools` | 查看当前会话可用工具 |
| `/skills` | 查看可用 skills |
| `/personas` | 查看可用 personas |
| `/state` | 查看当前引擎状态 |
| `/<skill-name>` | 手动触发某个 skill |

## 配置说明

核心运行时配置位于 `config.yaml`。

| 配置项 | 说明 |
| --- | --- |
| `default_provider` | 新会话默认模型 Provider |
| `providers` | OpenAI-compatible 与 Anthropic 风格 Provider 定义 |
| `engine.max_rounds` | 单次任务最大模型/工具循环轮数 |
| `compression` | 上下文窗口、触发比例、近期消息保留数和摘要 Provider |
| `storage` | SQLite 或内存存储后端 |
| `tools.enabled` | 全局启用工具列表 |
| `tools.confirm_tools` | 需要人工确认的工具 |
| `tools.limits` | 单个工具的输出和执行限制 |
| `mcp_servers` | 可选 MCP 服务定义 |

`config.yaml` 支持环境变量展开。API Key 和其他敏感信息应放在 `.env`，不要提交到源码仓库。

## 内置工具

| 工具 | 用途 |
| --- | --- |
| `read_file`, `write_file`, `edit_file`, `create_directory`, `list_dir` | 文件系统操作 |
| `write_json` | 结构化 JSON 写入 |
| `search`, `grep`, `glob` | 代码和文本搜索 |
| `shell`, `powershell` | 本地命令执行 |
| `web_search`, `web_fetch` | 网页搜索与网页正文抓取 |
| `image_generate`, `image_edit` | 设计图片生成与编辑 |
| `todo_write` | 创建和更新可见计划 |
| `memory` | 持久化记忆读写 |
| `think` | 用于运行轨迹展示的显式推理记录 |
| `background_task` | 后台长任务 |
| `spawn_agent`, `spawn_agents` | 创建子智能体 |
| `use_skill` | 按需加载完整 skill 指令 |

## Personas、Skills 与 Commands

项目本地行为配置集中在 `.myharness/`：

```text
.myharness/
|-- personas/       # builder、planner、reviewer 等智能体角色
|-- skills/         # 可复用流程知识，每个 skill 包含 SKILL.md
|-- commands/       # 项目命令
`-- transcripts/    # 运行过程 transcript
```

### Personas

Persona 定义智能体身份、系统提示词、默认 Provider、审批模式和可用工具。典型角色包括：

- `builder`：实现与交付
- `planner`：任务拆解与计划
- `reviewer`：质量审查与风险识别
- `researcher`：资料收集与综合分析
- `docs-writer`：文档编写

### Skills

Skill 用来沉淀可复用流程。会话启动时，引擎会把 skill 名称和描述注入 prompt；完整内容只有在智能体调用 `use_skill` 时才加载。这样既能保持 prompt 轻量，又能支持专业流程。

### Commands

Command 用于定义项目级快捷动作。它们可以通过 CLI 或 Web UI 暴露出来，作为常见任务模板复用。

## Web UI 能力

Web Workspace 由 FastAPI 后端和 WebSocket 事件驱动，主要支持：

- 创建、恢复、切换、重命名、置顶、归档和删除会话。
- 选择 Provider、Persona、审批模式和提问模式。
- 实时查看消息、工具调用、工具结果、状态变化和运行错误。
- 展开工具调用详情，观察智能体实际执行了什么。
- 编辑历史用户消息，并从该位置重新生成。
- 查看和编辑项目 skills、personas 与运行配置。

## 提问模式

Atelier 支持两种会话级提问模式：

| 模式 | 行为 | 适用场景 |
| --- | --- | --- |
| `noquestion` | 默认直接执行，必要时在最终回复中说明关键假设 | 需求清晰、希望快速完成 |
| `question` | 允许智能体在关键信息缺失时主动提出结构化澄清问题 | 复杂任务、设计目标不明确或决策成本较高 |

CLI 示例：

```bash
python cli.py --persona builder --question-mode question
```

REST 示例：

```bash
curl -X PATCH http://localhost:8000/sessions/{session_id}/mode \
  -H "Content-Type: application/json" \
  -d '{"question_mode": "question"}'
```

## REST 与 WebSocket API

常用 REST 端点：

| Endpoint | 用途 |
| --- | --- |
| `POST /sessions` | 创建或恢复会话 |
| `GET /sessions` | 获取会话列表 |
| `GET /sessions/{id}/state` | 获取完整会话快照 |
| `POST /sessions/{id}/messages` | 发送用户消息 |
| `PATCH /sessions/{id}/messages/{message_id}` | 编辑历史消息，可选择重新生成 |
| `POST /sessions/{id}/continue` | 从可恢复状态继续 |
| `POST /sessions/{id}/cancel` | 取消运行中任务 |
| `POST /sessions/{id}/confirm` | 确认待审批工具调用 |
| `POST /sessions/{id}/deny` | 拒绝待审批工具调用 |
| `PATCH /sessions/{id}/approval-mode` | 切换审批模式 |
| `PATCH /sessions/{id}/mode` | 切换提问模式 |
| `GET /config/agents` | 列出 Agent profiles |
| `GET /memory` / `POST /memory` | 管理 memory |
| `GET /commands` | 列出项目命令 |
| `WS /ws/{session_id}` | 推送运行时事件 |

WebSocket 事件包括 token、message、state、tool result、question asked/resolved 等。前端应始终以后端状态为准。

## 安全与权限

Atelier 是本地研究型 Agent Harness。它已经包含实用的安全控制，但生产部署或多用户场景仍需要额外审查。

已有控制包括：

- Shell / PowerShell 等高风险工具可要求人工确认。
- Persona 可以限制单个会话可用工具。
- 工具输出有长度上限，降低上下文溢出风险。
- 敏感配置通过环境变量注入。
- `web_fetch` 工具包含基础 SSRF 防护。
- 运行状态由显式状态机控制。

在暴露给不可信用户之前，建议：

- 使用最小权限 persona。
- 禁用不需要的 shell 类工具。
- 将服务运行在受控网络内。
- 增加鉴权、限流和审计日志。
- 检查 `.env`、SQLite 数据库和生成产物目录的访问权限。

## 开发与测试

运行完整测试：

```bash
pytest
```

常用定向测试：

```bash
pytest tests/test_engine.py
pytest tests/test_tools.py
pytest tests/test_storage.py
pytest tests/test_streaming.py
pytest tests/test_question_mode.py
```

统计代码量：

```bash
python scripts/loc.py
```

## 发布检查清单

- [ ] `.env.example` 已覆盖必要配置，真实 `.env` 未提交。
- [ ] `config.yaml` 默认 Provider 与文档中的环境变量一致。
- [ ] 高风险工具已列入 `tools.confirm_tools`。
- [ ] Web UI 可通过 `uvicorn api.rest:app --port 8000` 启动。
- [ ] CLI 可通过 `python cli.py --persona builder` 启动。
- [ ] 核心测试通过。
- [ ] README 图片链接、命令和接口说明与当前代码一致。
- [ ] License 文件存在且符合发布要求。

## 路线图

- 设计领域工具：素材调研、视觉分析、版式评审、品牌系统生成。
- 更完整的产物工作流：brief、设计批次、评审记录和最终导出包。
- 更细粒度权限：按目录、工具、Provider 和会话限制能力。
- 更完整的 Web UI：运行轨迹、文件预览、产物画廊和子智能体视图。
- 更强的记忆管理：项目偏好、长期约束和可编辑 memory。
- 生产部署支持：鉴权、多用户隔离、队列、审计日志和监控。

## 常见问题

**为什么启动时报 Provider 不存在？**

检查 `config.yaml` 中的 provider 名称，并确认 `.env` 里的 `HARNESS_DEFAULT_PROVIDER` 指向其中一个名称。

**为什么网页搜索没有有效结果？**

如果没有配置 `SERPER_API_KEY` 或 `BRAVE_SEARCH_API_KEY`，`web_search` 会降级到能力有限的 DuckDuckGo instant-answer fallback。完整网页搜索建议配置 Serper 或 Brave。

**为什么不建议使用 `uvicorn --reload`？**

智能体执行任务时可能会写文件。`--reload` 会监听文件变化并重启服务，从而中断当前会话。

**Skill 没有自动触发怎么办？**

检查 `.myharness/skills/<skill-name>/SKILL.md` 中的 description 是否清晰说明使用场景。也可以通过 `/<skill-name>` 手动调用。

**如何让智能体会话更安全？**

在 persona 中设置 `allowed_tools`，并在 `config.yaml` 中禁用不必要工具。Shell 类工具建议保持审批模式。

## 项目状态

Atelier 是一个持续迭代中的研究型产品底座。通用智能体运行时、工具系统、持久化会话、Web/CLI 入口和基础多智能体能力已经实现；设计领域工具、产物管理、权限加固和生产部署能力仍在持续开发中。

## License

Atelier 使用 [MIT License](LICENSE) 开源。
