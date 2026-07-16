# Atelier

[English](README.md) | [简体中文](README.zh-CN.md)

Atelier is a lightweight, independently developed agent scaffold from our lab for building professional design-oriented AI agents. It provides the runtime foundation for future design workflows: project-aware sessions, tool execution, planning, memory, skills, sub-agents, human approval, and live execution traces across both a Web UI and a CLI.

The current repository focuses on the general-purpose harness layer before domain-specific design tools are fully added. In other words, this is the infrastructure layer for design agents: not just a chat wrapper around an LLM API, but a controllable runtime where an agent can reason, act, ask for clarification, operate tools, persist context, recover from errors, and collaborate through sub-agents.

## Highlights

- **Design-agent scaffold**: a lightweight foundation for future professional design workflows, including research, planning, iteration, critique, and artifact-oriented tool use.
- **Web and CLI entry points**: use the browser-based workspace or run directly from `cli.py`.
- **OpenAI-compatible and Anthropic providers**: configure models through `config.yaml` and environment variables.
- **Tool registry and executor**: file operations, shell / PowerShell, web search, web fetch, thinking, memory, todo planning, background tasks, and sub-agent spawning.
- **Approval modes**: ask before risky actions, allow automatic execution, or run with full permission depending on the selected agent/session mode.
- **Session persistence**: SQLite-backed sessions, metadata, checkpoints, visible plan state, and memory entries.
- **Live runtime visibility**: REST + WebSocket streaming for messages, tool calls, tool results, plan updates, approvals, and recovery events.
- **Skills and agent profiles**: project-local personas and skills are discovered from `.myharness/` and injected into the prompt context.
- **Multi-agent support**: parent sessions can spawn child sessions while preserving session lineage.
- **Context management**: automatic compression and prompt caching keep long sessions usable.

## What This Harness Provides

Atelier is organized as a set of runtime layers that can be reused when building a design-focused agent product.

### Entry Layer

The project supports three main access paths:

- **Web UI** through `static/index.html`, backed by FastAPI.
- **CLI** through `cli.py` for local interactive use.
- **REST / WebSocket API** through `api/rest.py` and `api/ws.py` for integration with other interfaces.

This keeps the agent runtime independent from a single frontend. A future design workspace can reuse the same backend while replacing or extending the UI.

### Session Layer

Sessions are persistent units of work. Each session stores messages, metadata, title, selected agent, provider, approval mode, question mode, plan state, and parent-child relationships for sub-agents.

The Web UI can list, reopen, rename, pin, archive, and delete sessions. The backend restores session state from SQLite so long-running design work can continue across browser refreshes or server restarts.

### Agent Runtime Layer

The runtime is a ReAct-style loop:

```text
assemble prompt -> call model -> parse tool calls -> execute tools -> store results -> continue or answer
```

Unlike a single-turn chatbot, the loop is designed for long tasks. It can continue after tool execution, surface intermediate progress, stop for approval, ask the user for clarification, and recover from some interrupted states.

### Model Layer

The provider registry supports OpenAI-compatible chat-completion endpoints and Anthropic-style providers. Model configuration is declared in `config.yaml`, while secrets remain in `.env`.

This makes the harness portable across model vendors and local proxy services.

### Prompt and Agent Profile Layer

Agent profiles live under `.myharness/personas/`. A profile can define the agent's role, system prompt, default provider, default approval mode, and allowed tools.

The current profiles are general building blocks such as builder, planner, reviewer, debugger, researcher, and docs-writer. Future design-specific agents can be added in the same format, for example design-researcher, layout-critic, prototype-builder, or visual-spec-writer.

### Tool Layer

Tools are registered through a central registry and executed by a tool executor. Built-in tools cover file editing, search, shell execution, web access, memory, planning, background tasks, and sub-agent creation.

MCP tools can also be bridged into the registry, but the harness keeps its own core tools so local workflows do not depend entirely on external MCP behavior.

### Skill Layer

Skills are reusable procedural knowledge. The harness scans project skills, injects short descriptions into the prompt, and loads full skill content only when the agent explicitly requests it.

This two-stage loading pattern keeps the prompt compact while still allowing specialized design or engineering procedures to be pulled in when needed.

### Context and Memory Layer

The harness keeps conversation messages, persistent memory entries, visible plan state, checkpoints, and compressed summaries. Compression is triggered when the context grows large, preserving recent messages while summarizing older context.

For design workflows, this layer is intended to preserve project decisions, user preferences, critique notes, and reusable constraints across sessions.

### Safety and Approval Layer

Risky tools such as shell and PowerShell can require confirmation. Approval mode can be changed per session, and agent profiles can restrict which tools are available.

This is important for design agents that may edit files, generate artifacts, run commands, or call external services.

### Human Collaboration Layer

The agent can ask structured questions instead of guessing unclear requirements. User replies resume the same engine run, which supports workflows such as clarifying design goals before planning or implementation.

### Multi-Agent Layer

The runtime supports sub-agent sessions through `spawn_agent` and `spawn_agents`. Sub-agents keep their own context while remaining linked to a parent session.

This makes it possible to split design work into roles such as research, planning, implementation, review, and documentation.

### Runtime Visibility Layer

The Web UI receives runtime events through WebSocket. It can show model rounds, tool calls, tool results, plan updates, approval prompts, recovery notices, and intermediate thinking/tool traces.

This visibility is central to the project: users should be able to inspect what the design agent is doing, not just receive a final answer.

## Repository Layout

```text
.
|-- api/                    # FastAPI REST and WebSocket server
|-- harness/                # Agent runtime, tools, storage, LLM providers
|   |-- engine/             # Main loop, state machine, compression, prompt cache
|   |-- tools/              # Built-in tools and execution layer
|   |-- storage/            # SQLite / memory backends, plan and memory stores
|   |-- llm/                # Provider abstraction and implementations
|   |-- mcp/                # MCP bridge and transports
|   `-- commands/           # Built-in and project command system
|-- static/                 # Browser UI
|-- .myharness/             # Project agents, skills, commands, transcripts
|-- tests/                  # Unit and integration tests
|-- cli.py                  # Interactive CLI entry point
|-- config.yaml             # Runtime configuration
`-- pyproject.toml          # Python package metadata
```

## Quick Start

### 1. Install

Python 3.11 or newer is required.

```bash
pip install -e ".[dev]"
```

### 2. Configure Environment

Create a `.env` file from `.env.example`, then fill in the provider you want to use.

For the default OpenAI-compatible provider:

```env
OPENAI_HUB_API_KEY=your-api-key
OPENAI_HUB_BASE_URL=https://api.openai-hub.com/v1
OPENAI_HUB_MODEL=gpt-4o
HARNESS_DEFAULT_PROVIDER=openai-hub
```

For web search, configure Serper if you need real search results:

```env
SERPER_API_KEY=your-serper-key
```

Without a real search key, the `web_search` tool falls back to a limited DuckDuckGo instant-answer mode.

For design image generation and image editing, configure the image endpoints used by `image_generate` and `image_edit`:

```env
DESIGN_IMAGE_API_KEY=your-image-api-key
DESIGN_IMAGE_BASE_URL=https://api.openai-hub.com/v1
DESIGN_IMAGE_MODEL=gpt-image-2
DESIGN_IMAGE_ENDPOINT=https://api.openai-hub.com/v1/images/generations
DESIGN_IMAGE_EDIT_ENDPOINT=https://api.openai-hub.com/v1/images/edits
```

If `DESIGN_IMAGE_API_KEY` or `DESIGN_IMAGE_BASE_URL` are not set, the image tools fall back to `OPENAI_HUB_API_KEY` and `OPENAI_HUB_BASE_URL`. You can also set `DESIGN_IMAGE_DEFAULT_SIZE` such as `1024x1024`.

### 3. Start the Web UI

```bash
uvicorn api.rest:app --port 8000
```

Open:

```text
http://localhost:8000
```

For long-running agent tasks, avoid `--reload`. File-writing agents can trigger server reloads and interrupt an active session.

### 4. Or Use the CLI

```bash
python cli.py
python cli.py --persona builder
python cli.py --provider openai-hub
```

## Configuration

The main runtime configuration lives in `config.yaml`.

Important sections:

- `default_provider`: default model provider used by new sessions.
- `providers`: OpenAI-compatible and Anthropic provider definitions.
- `engine.max_rounds`: maximum loop rounds before the engine stops.
- `compression`: context window, trigger ratio, recent-message retention, and summary provider.
- `storage`: SQLite or in-memory backend.
- `tools.enabled`: globally enabled tools.
- `tools.confirm_tools`: tools that require confirmation before execution.
- `tools.limits`: per-tool output and execution limits.
- `mcp_servers`: optional MCP server definitions.

Environment variables are expanded from `config.yaml`, so secrets should stay in `.env` instead of being committed.

## Built-in Tools

Common built-in tools include:

| Tool | Purpose |
| --- | --- |
| `read_file`, `write_file`, `edit_file`, `create_directory`, `list_dir` | File-system work |
| `write_json` | Structured JSON file writing |
| `grep`, `glob`, `search` | Code and text search |
| `shell`, `powershell` | Local command execution |
| `web_search`, `web_fetch` | Web search and page retrieval |
| `image_generate`, `image_edit` | Design image generation and editing |
| `todo_write` | Visible plan creation and updates |
| `memory` | Persistent memory read/write |
| `think` | Explicit reasoning notes shown in the runtime trace |
| `background_task` | Long-running background work |
| `spawn_agent`, `spawn_agents` | Sub-agent creation |
| `use_skill` | Load full skill content on demand |

Tools are registered through the harness tool registry and are exposed to the model as callable functions. MCP tools can also be bridged into the same registry.

## Agents, Skills, and Commands

Project-local behavior is configured under `.myharness/`.

```text
.myharness/
├── personas/       # Agent profiles such as builder, planner, reviewer
├── skills/         # Reusable skill descriptions and full skill content
├── commands/       # Slash-style project commands
└── transcripts/    # Runtime transcript artifacts
```

Agent profiles control the system prompt, default provider, default approval mode, and allowed tools. Skills are loaded in two phases: a short description is injected into the prompt, while full skill content is loaded only when the agent calls the skill tool.

## Runtime Model

At a high level, each session runs the following loop:

```text
user input
  -> prompt assembly
  -> memory / plan / skill context injection
  -> compression if needed
  -> model call
  -> tool call execution
  -> tool result persistence
  -> next model round or final assistant response
```

The engine persists messages and session metadata, emits runtime events, and streams updates to the Web UI over WebSocket. This makes intermediate work visible instead of hiding the agent behind a single final response.

## Safety Model

Atelier includes several safety controls:

- Risky tools can require user confirmation.
- Approval mode can be changed per session.
- Agent profiles can restrict allowed tools.
- Tool output is capped to prevent context overflow.
- Shell execution uses explicit command arguments where possible.
- Runtime state transitions are checked by a state machine.

This is still a local research harness. Review `config.yaml` before exposing it to untrusted users or running it on sensitive machines.

## REST and WebSocket API

The Web UI talks to the backend through FastAPI.

Common endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /sessions` | Create or restore a session |
| `POST /sessions/{id}/messages` | Send a user message |
| `GET /sessions/{id}/state` | Read the full session snapshot |
| `POST /sessions/{id}/continue` | Continue from a recoverable state |
| `POST /sessions/{id}/cancel` | Cancel a running session |
| `POST /sessions/{id}/confirm` / `deny` | Resolve approval requests |
| `PATCH /sessions/{id}/approval-mode` | Change approval mode |
| `GET /config/agents` | List agent profiles |
| `GET /memory` / `POST /memory` | Manage memory entries |
| `GET /commands` | List project commands |
| `WS /ws/{session_id}` | Stream runtime events |

## Documentation

- [Developer Documentation Site](developer-docs/index.html)

## Development

Run tests:

```bash
pytest
```

Useful focused tests:

```bash
pytest tests/test_engine.py
pytest tests/test_tools.py
pytest tests/test_storage.py
pytest tests/test_streaming.py
```

## Project Status

This repository is an evolving academic / research harness and a foundation for a professional design-agent scaffold. Core runtime features are implemented, while design-domain tools, richer artifact workflows, permission hardening, UI polish, memory management, and production deployment still need iteration.

## License

Atelier is released under the [MIT License](LICENSE).
