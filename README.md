# Dreamatic

[English](README.md) | [简体中文](README.zh-CN.md)

**Harness for Professional Design Agents** — Direct creativity, orchestrate intelligence, deliver professional design.

![Dreamatic hero illustration](docs/assets/dreamatic-hero.png)

Dreamatic is a controllable agent runtime that goes beyond simple chat. Agents can understand requests, plan work, call tools, persist context, request human approval, spawn sub-agents, and stream execution in real time — all within persistent sessions.

The current release focuses on a general-purpose runtime layer suitable for design agents, research workspaces, local automation assistants, and multi-agent systems requiring predictable execution, tool governance, and observable long-running work.

![Dreamatic runtime architecture](docs/assets/dreamatic-architect.png)

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Fill in provider credentials
```

Basic OpenAI-compatible setup:

```env
DREAMATIC_API_KEY=your-api-key
DREAMATIC_BASE_URL=https://your-endpoint/v1
DREAMATIC_MODEL=gpt-4o
HARNESS_DEFAULT_PROVIDER=openai-hub
```

For full web search:

```env
SERPER_API_KEY=your-serper-key
BRAVE_SEARCH_API_KEY=your-brave-key
```

For image generation and editing:

```env
DREAMATIC_IMAGE_API_KEY=your-image-api-key
DREAMATIC_IMAGE_BASE_URL=https://your-image-endpoint/v1
DREAMATIC_IMAGE_MODEL=gpt-image-2
DREAMATIC_IMAGE_GENERATION_ENDPOINT=https://your-image-endpoint/v1/images/generations
DREAMATIC_IMAGE_EDIT_ENDPOINT=https://your-image-endpoint/v1/images/edits
DREAMATIC_IMAGE_DEFAULT_SIZE=1024x1024
```

### 3. Start Web UI

```bash
uvicorn api.rest:app --port 8000
# Open http://localhost:8000
```

### 4. Or use CLI

```bash
python cli.py --persona builder
```

## Key Features

| Area | Capabilities |
| --- | --- |
| **Entry points** | Web UI, interactive CLI, REST + WebSocket API |
| **Agent runtime** | ReAct-style loop with cancellation, recovery, and real-time streaming |
| **Model providers** | OpenAI-compatible and Anthropic; configured via `config.yaml` and `.env` |
| **Built-in tools** | 20+ tools: file ops, search, shell, web search/fetch, image gen/edit, memory, planning, sub-agents |
| **Persistence** | SQLite-backed messages, plans, memory, checkpoints, and session relationships |
| **Security** | Per-tool approval gates, persona-scoped permissions, output limits, SSRF protection |
| **Extensibility** | Personas (agent roles), Skills (reusable procedures), Commands (project shortcuts), MCP bridge |
| **Context management** | Automatic compression and prompt caching for long-running sessions |
| **Multi-agent** | Parent sessions spawn sub-agents for research, planning, review, and documentation |
| **Observability** | WebSocket streams model rounds, tool calls, results, plan changes, and approval events |

## Architecture

Dreamatic is organized into six runtime layers. See [`docs/architecture-overview.md`](docs/architecture-overview.md) for the full system diagram with component details.

```mermaid
graph TB
    classDef entry fill:#e3f2fd,stroke:#1976d2
    classDef session fill:#eceff1,stroke:#546e7a
    classDef runtime fill:#bbdefb,stroke:#1976d2
    classDef tool fill:#e0f2f1,stroke:#00897b
    classDef llm fill:#fff3e0,stroke:#f57c00
    classDef ext fill:#e0f2f1,stroke:#00897b
    classDef store fill:#f3e5f5,stroke:#7b1fa2
    classDef observe fill:#fce4ec,stroke:#c62828

    subgraph Entry["ENTRY — Web UI / CLI / REST / WebSocket"]
        WebUI("Web Workspace&lt;br/&gt;SPA · sessions · preview"):::entry
        CLI("Interactive CLI&lt;br/&gt;REPL · personas · commands"):::entry
        API("REST + WebSocket API&lt;br/&gt;FastAPI · 30+ endpoints"):::entry
    end

    subgraph Session["SESSION — Lifecycle &amp; governance"]
        SessLife("create · restore · archive · delete"):::session
        SessMeta("metadata · title · tags · lineage"):::session
        SessMode("question_mode · approval_mode"):::session
    end

    subgraph Runtime["AGENT RUNTIME — Core execution engine"]
        StateM("State Machine&lt;br/&gt;6 states: WAITING_INPUT → RUNNING →&lt;br/&gt;WAITING_CONFIRMATION / WAITING_INTERRUPT →&lt;br/&gt;COMPLETED / ERROR"):::runtime
        React("ReAct Controller&lt;br/&gt;1. cancel check 2. compress 3. repair 4. load schemas&lt;br/&gt;5. LLM call 6. loop detect 7. confirm gate&lt;br/&gt;8. execute tools 9. append 10. check interrupt"):::runtime
        Prompt("Prompt Assembly&lt;br/&gt;system · persona · skills · memory · plan · history"):::runtime
        Context("Context Manager&lt;br/&gt;compression · prompt cache · micro + auto"):::runtime
        Approve("Approval Gate&lt;br/&gt;ask · auto · full"):::runtime
        Cancel("Cancel &amp; Recovery&lt;br/&gt;auto-retry · interrupt signal"):::runtime
    end

    subgraph ToolProvider["TOOL &amp; PROVIDER"]
        ToolReg("ToolRegistry&lt;br/&gt;30+ tools · schema + handler"):::tool
        ToolExec("ToolExecutor&lt;br/&gt;async gather · overflow store"):::tool
        Tools("File · Search · Shell · Web&lt;br/&gt;Image · Agent · Design · Core"):::tool
        OpenAI("OpenAI Provider&lt;br/&gt;stream_chat · tool use"):::llm
        Anthropic("Anthropic Provider&lt;br/&gt;extended thinking"):::llm
    end

    subgraph Extension["EXTENSION — Plugins &amp; customization"]
        Personas("Personas&lt;br/&gt;builder · planner · reviewer"):::ext
        Skills("Skills&lt;br/&gt;reusable procedures"):::ext
        Commands("Commands&lt;br/&gt;slash shortcuts"):::ext
        MCP("MCP Bridge&lt;br/&gt;stdio · HTTP transport"):::ext
    end

    subgraph Storage["STORAGE — Persistence"]
        SessSt("SessionStore&lt;br/&gt;messages · metadata"):::store
        MemSt("MemoryStore&lt;br/&gt;long-term memory"):::store
        PlanSt("PlanStore&lt;br/&gt;plans · checkpoints"):::store
        Backend("SQLite / In-Memory"):::store
    end

    subgraph Observe["OBSERVABILITY — Streaming &amp; audit"]
        Events("EventEmitter&lt;br/&gt;structured JSON logs"):::observe
        WSStream("WebSocket Stream&lt;br/&gt;token · state · question.*"):::observe
        Hooks("Hook System&lt;br/&gt;before/after LLM &amp; tool"):::observe
    end

    API -->|"send_message()"| React
    CLI -->|"asyncio.run"| React
    React -->|"state transitions"| StateM
    React -->|"stream_chat()"| OpenAI
    React -->|"stream_chat()"| Anthropic
    OpenAI -->|"ToolCallBlock"| React
    React -->|"execute"| ToolExec
    ToolExec -->|"dispatch"| ToolReg
    ToolReg -->|"call"| Tools
    ToolExec -.->|"hooks"| Hooks
    React -->|"save/load"| SessSt
    React -->|"read/write"| MemSt
    React -.->|"emit"| Events
    Events -.->|"push"| WSStream
    Personas -.->|"restrict"| ToolReg
    MCP -.->|"register"| ToolReg
    SessSt -.->|"backed by"| Backend
    MemSt -.->|"backed by"| Backend
    PlanSt -.->|"backed by"| Backend
```

| Layer | Responsibility |
|---|---|
| Entry | Web UI, CLI, REST API, WebSocket streaming |
| Session | Create, restore, rename, pin/archive, parent-child relationships, runtime modes |
| Agent runtime | State machine (6 states), ReAct controller, prompt assembly, context compression, prompt cache |
| Tool & Provider | 30+ built-in tools, OpenAI-compatible & Anthropic LLM providers, MCP bridge |
| Extension | Personas (roles), Skills (procedures), Commands (shortcuts), MCP bridge |
| Storage | SQLite or in-memory backends for SessionStore, MemoryStore, PlanStore, CheckpointStore |

**Execution flow**: User sends a request → engine assembles prompt (system + persona + skills + memory + plan + history) → model responds or requests tool calls → tools pass through approval gate → results stream to frontend → loop continues or final answer returned.

## Design Examples

Each example includes a full-resolution final package and artifact gallery.

### Brand & Merchandise: Jingju Guochao Series

A cultural merchandise system inspired by Peking opera facial makeup. [Open package](examples/jingju-guochao-merch/final/00-index.html)

| Product system | Packaging | Series overview |
|---|---|---|
| <img src="examples/jingju-guochao-merch/final/artifacts/generated-images/01-product-overview.png" width="220"> | <img src="examples/jingju-guochao-merch/final/artifacts/generated-images/07-packaging-application.png" width="220"> | <img src="examples/jingju-guochao-merch/final/artifacts/generated-images/10-series-overview.png" width="220"> |

### Brand & Merchandise: Tongji IDVX Lab

Lab merchandise — bags, notebooks, badges. [Open package](examples/tongji-idvx-lab-merch/final/00-index.html)

| Tote hero | Notebook cover | Badge system |
|---|---|---|
| <img src="examples/tongji-idvx-lab-merch/final/artifacts/generated-images/01-tote-hero-front.png" width="220"> | <img src="examples/tongji-idvx-lab-merch/final/artifacts/generated-images/03-notebook-cover.png" width="220"> | <img src="examples/tongji-idvx-lab-merch/final/artifacts/generated-images/05-badge-set-board.png" width="220"> |

### Product Design: Elderly AI Companion Device

A companion device concept for elderly living alone. [Open package](examples/elderly-ai-companion-device/final/00-index.html)

| Hero render | Three-view | CMF board |
|---|---|---|
| <img src="examples/elderly-ai-companion-device/final/artifacts/generated-images/01-hero-render.png" width="220"> | <img src="examples/elderly-ai-companion-device/final/artifacts/generated-images/02-three-view.png" width="220"> | <img src="examples/elderly-ai-companion-device/final/artifacts/generated-images/06-cmf-board.png" width="220"> |

### Architecture: Zhujiajiao Visitor Center

Visitor center concept for an ancient water town. [Open package](examples/zhujiajiao-visitor-center-space/final/00-index.html)

| Site context | Zoning | Entry hall |
|---|---|---|
| <img src="examples/zhujiajiao-visitor-center-space/final/artifacts/generated-images/01-site-context-relation.png" width="220"> | <img src="examples/zhujiajiao-visitor-center-space/final/artifacts/generated-images/02-master-plan-zoning.png" width="220"> | <img src="examples/zhujiajiao-visitor-center-space/final/artifacts/generated-images/06-hero-entry-hall.png" width="220"> |

### Poster & Advertising: IEEE VIS 2026

Conference promotion — posters, social media, badges, templates. [Open package](examples/ieee-vis-2026-promo/final/00-index.html)

| Main poster | Key visual | Social post |
|---|---|---|
| <img src="examples/ieee-vis-2026-promo/final/artifacts/generated-images/01-main-poster.png" width="220"> | <img src="examples/ieee-vis-2026-promo/final/artifacts/generated-images/02-key-visual.png" width="220"> | <img src="examples/ieee-vis-2026-promo/final/artifacts/generated-images/05-social-twitter-post.png" width="220"> |

### Campus Campaign: Shanghai Innovation Institute

Bilingual campaign with merch mockups and moodboards. [Open package](examples/shanghai-chuangzhi-college-merch-system/final/00-index.html)

| Logo poster | Chinese poster | Merch mockup |
|---|---|---|
| <img src="examples/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/01-logo-application-poster.png" width="220"> | <img src="examples/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/02-campaign-poster-zh.png" width="220"> | <img src="examples/shanghai-chuangzhi-college-merch-system/final/artifacts/generated-images/07-merch-mockup.png" width="220"> |

## Repository Layout

```
.
|-- api/                # FastAPI REST + WebSocket server
|-- harness/            # Agent runtime, tools, storage, LLM providers
|   |-- engine/         # Main loop, state machine, compression, prompt cache
|   |-- tools/          # Built-in tools and execution layer
|   |-- storage/        # SQLite and in-memory backends
|   |-- llm/            # Provider abstraction and implementations
|   |-- mcp/            # MCP bridge and transports
|   `-- commands/       # Built-in and project command system
|-- static/             # Browser frontend
|-- .myharness/         # Personas, skills, commands, transcripts
|-- tests/              # Tests
|-- cli.py              # CLI entry point
|-- config.yaml         # Runtime configuration
`-- pyproject.toml
```

## Configuration

### config.yaml

| Setting | Description |
|---|---|
| `default_provider` | Default model provider |
| `providers` | Provider definitions (OpenAI-compatible / Anthropic) |
| `engine.max_rounds` | Max model/tool loop rounds per task |
| `compression` | Token window, trigger ratio, summary provider |
| `storage` | SQLite or in-memory |
| `tools.enabled` | Globally enabled tools |
| `tools.confirm_tools` | Tools requiring human confirmation |
| `tools.limits` | Per-tool output/execution limits |
| `mcp_servers` | Optional MCP server definitions |

### Personas, Skills, Commands

Project-local behavior in `.myharness/`:

```
.myharness/
|-- personas/    # Agent roles (builder, planner, reviewer, etc.)
|-- skills/      # Reusable procedures (SKILL.md per skill)
|-- commands/    # Project-level shortcuts
`-- transcripts/ # Runtime transcripts
```

**Personas** define system prompt, default provider, approval mode, and allowed tools. **Skills** are injected by name at startup; full content loads on `use_skill`. **Commands** are project shortcuts exposed via CLI and Web UI.

### Built-in Tools

| Tool | Purpose |
|---|---|
| `read_file`, `write_file`, `edit_file`, `create_directory`, `list_dir`, `write_json` | File operations |
| `search`, `grep`, `glob` | Code/text search |
| `shell`, `powershell` | Local command execution |
| `web_search`, `web_fetch` | Web search and page extraction |
| `image_generate`, `image_edit` | Image generation and editing |
| `todo_write` | Plan creation and updates |
| `memory` | Persistent memory read/write |
| `think` | Explicit reasoning notes |
| `background_task` | Long-running background work |
| `spawn_agent`, `spawn_agents` | Sub-agent creation |
| `use_skill` | Load skill instructions on demand |

## Web UI

The Web Workspace supports creating, switching, renaming, pinning, archiving, and deleting sessions; selecting provider/persona/approval mode; real-time message and tool-call viewing; historical message editing with regeneration; and editing skills/personas/config.

## Question Mode

Two session-level modes: `noquestion` (direct execution, default) and `question` (agent asks clarification when information is missing).

```bash
python cli.py --persona builder --question-mode question
curl -X PATCH http://localhost:8000/sessions/{id}/mode \
  -H "Content-Type: application/json" \
  -d '{"question_mode": "question"}'
```

## REST & WebSocket API

| Endpoint | Purpose |
|---|---|
| `POST /sessions` | Create/restore session |
| `GET /sessions` | List sessions |
| `GET /sessions/{id}/state` | Session snapshot |
| `POST /sessions/{id}/messages` | Send message |
| `PATCH /sessions/{id}/messages/{mid}` | Edit & optionally regenerate |
| `POST /sessions/{id}/continue` | Continue from recoverable state |
| `POST /sessions/{id}/cancel` | Cancel running task |
| `POST /sessions/{id}/confirm` / `deny` | Approve/deny pending tool call |
| `PATCH /sessions/{id}/approval-mode` | Change approval mode |
| `PATCH /sessions/{id}/mode` | Change question mode |
| `GET /config/agents` | List agent profiles |
| `GET /memory` / `POST /memory` | Manage memory |
| `GET /commands` | List project commands |
| `WS /ws/{session_id}` | Stream runtime events |

## Security

Built-in controls: approval gates for high-risk tools (shell, powershell), persona-scoped tool permissions, output caps, env-var secrets, SSRF protection in web_fetch, explicit state machine for runtime transitions. For untrusted-user exposure, use least-privilege personas, disable unnecessary tools, run in a controlled network, and add authentication/rate limiting/audit logging.

## Development

```bash
pytest                              # Full suite
pytest tests/test_engine.py         # Engine tests
python scripts/loc.py               # Count lines of code
```

## FAQ

**Provider not found?** — Check provider names in `config.yaml` and `HARNESS_DEFAULT_PROVIDER` in `.env`.

**Web search empty?** — Set `SERPER_API_KEY` or `BRAVE_SEARCH_API_KEY`; fallback is limited DuckDuckGo.

**Avoid `uvicorn --reload`?** — File writes from agents can trigger restart and interrupt sessions.

**Skill not auto-invoked?** — Check its `SKILL.md` description is clear. Use `/<skill-name>` to invoke manually.

## License

[MIT License](LICENSE)
