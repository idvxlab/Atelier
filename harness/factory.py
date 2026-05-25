"""
Engine factory — single source of truth for building an AgentEngine.

Both cli.py and api/rest.py import build_engine() from here.
To add a new tool, register it in ALL_TOOLS and add it to config.yaml tools.enabled.

MCP Support
-----------
Use ``build_engine_with_mcp()`` (async) when config.yaml has ``mcp_servers``
defined.  It returns ``(AgentEngine, list[MCPClient])``; callers are responsible
for calling ``await client.close()`` on each MCPClient when done.
"""
from __future__ import annotations

import logging

from harness.config import HarnessConfig, ProviderConfig
from harness.engine.compression import CompressionConfig, ContextCompressor
from harness.engine.engine import AgentEngine, EngineConfig
from harness.engine.loop import ReactLoop
from harness.llm.registry import build_provider
from harness.observability.events import EventEmitter
from harness.skills import list_skills, build_skill_system_addendum
from harness.storage.session import SessionStore
from harness.tools.builtin import (
    READ_FILE_SCHEMA, read_file_tool,
    SEARCH_SCHEMA, search_tool,
    SHELL_SCHEMA, shell_tool,
    USE_SKILL_SCHEMA, use_skill_tool,
    GLOB_SCHEMA, glob_tool,
    GREP_SCHEMA, grep_tool,
    POWERSHELL_SCHEMA, powershell_tool,
    WRITE_FILE_SCHEMA, write_file_tool,
    EDIT_FILE_SCHEMA, edit_file_tool,
    WEB_FETCH_SCHEMA, web_fetch_tool,
    WEB_SEARCH_SCHEMA, web_search_tool,
    THINK_SCHEMA, think_tool,
    TODO_WRITE_SCHEMA, todo_write_tool,
)
from harness.tools.executor import ToolExecutor
from harness.tools.overflow import OverflowStore
from harness.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Central tool registry — add new tools here only
ALL_TOOLS: dict[str, tuple] = {
    "read_file":   (READ_FILE_SCHEMA,   read_file_tool),
    "write_file":  (WRITE_FILE_SCHEMA,  write_file_tool),
    "edit_file":   (EDIT_FILE_SCHEMA,   edit_file_tool),
    "search":      (SEARCH_SCHEMA,      search_tool),
    "shell":       (SHELL_SCHEMA,       shell_tool),
    "glob":        (GLOB_SCHEMA,        glob_tool),
    "grep":        (GREP_SCHEMA,        grep_tool),
    "powershell":  (POWERSHELL_SCHEMA,  powershell_tool),
    "web_fetch":   (WEB_FETCH_SCHEMA,   web_fetch_tool),
    "web_search":  (WEB_SEARCH_SCHEMA,  web_search_tool),
    "think":       (THINK_SCHEMA,       think_tool),
    "todo_write":  (TODO_WRITE_SCHEMA,  todo_write_tool),
}


def build_engine(
    session_id: str,
    provider_cfg: ProviderConfig,
    harness_cfg: HarnessConfig,
    session_store: SessionStore,
    system_prompt: str = "",
    allowed_tools: list[str] | None = None,
    registry: ToolRegistry | None = None,
    spawn_depth: int = 0,
) -> AgentEngine:
    """
    Build a fully wired AgentEngine for a session.

    Args:
        session_id:    Unique session identifier.
        provider_cfg:  LLM provider config (model, api_key, etc.).
        harness_cfg:   Global harness config (compression, tools, engine settings).
        session_store: Where to persist messages (MemorySessionStore or SQLiteSessionStore).
        system_prompt: Base system prompt. Skill descriptions are appended automatically.
        allowed_tools: Persona-level tool whitelist. None means use global config.
        registry:      Pre-built ToolRegistry (e.g. pre-populated with MCP tools).
                       When None, a fresh registry is created from ALL_TOOLS.
        spawn_depth:   Current agent nesting depth (0 = top-level). Used to limit
                       recursive sub-agent creation via spawn_agent/spawn_agents.
    """
    emitter = EventEmitter(session_id)
    llm = build_provider(provider_cfg)

    comp = harness_cfg.compression
    summarizer = (
        build_provider(harness_cfg.providers[comp.summary_provider])
        if comp.summary_provider and comp.summary_provider in harness_cfg.providers
        else llm
    )

    skills = list_skills()
    full_system = system_prompt + build_skill_system_addendum(skills)

    compressor = ContextCompressor(
        summarizer=summarizer,
        config=CompressionConfig(
            token_window=comp.token_window,
            auto_trigger_ratio=comp.auto_trigger_ratio,
            micro_keep_recent=comp.micro_keep_recent,
            system_identity=full_system,
        ),
    )

    # Resolve which tools to load:
    #   persona allowed_tools  ∩  global enabled  (or all if global is None)
    global_enabled = harness_cfg.tools.enabled
    if allowed_tools is not None:
        tools_to_load = [t for t in allowed_tools if global_enabled is None or t in global_enabled]
    else:
        tools_to_load = global_enabled if global_enabled is not None else list(ALL_TOOLS.keys())

    logger.info(
        "[build_engine] session=%s | ALL_TOOLS keys=%s",
        session_id, list(ALL_TOOLS.keys()),
    )
    logger.info(
        "[build_engine] session=%s | global_enabled=%s | allowed_tools=%s | tools_to_load=%s",
        session_id, global_enabled, allowed_tools, tools_to_load,
    )

    if registry is None:
        registry = ToolRegistry()
    for name in tools_to_load:
        if name in ALL_TOOLS:
            schema, handler = ALL_TOOLS[name]
            registry.register(schema, handler)
            logger.info("[build_engine] registered tool: %s", name)
        else:
            logger.warning("[build_engine] tool '%s' in tools_to_load but NOT in ALL_TOOLS — skipped", name)

    # use_skill is always available if skills exist (not controlled by allowed_tools)
    if skills:
        registry.register(USE_SKILL_SCHEMA, use_skill_tool)

    # spawn_agent / spawn_agents: registered conditionally by depth (not via ALL_TOOLS
    # because they need runtime dependencies passed as closure args)
    from harness.tools.builtin.spawn_agent import (
        SPAWN_AGENT_SCHEMA, make_spawn_agent_tool,
        SPAWN_AGENTS_SCHEMA, make_spawn_agents_tool,
        MAX_SPAWN_DEPTH,
    )
    if spawn_depth < MAX_SPAWN_DEPTH:
        registry.register(
            SPAWN_AGENT_SCHEMA,
            make_spawn_agent_tool(harness_cfg, provider_cfg, session_store, spawn_depth),
        )
        registry.register(
            SPAWN_AGENTS_SCHEMA,
            make_spawn_agents_tool(harness_cfg, provider_cfg, session_store, spawn_depth),
        )

    # Append the definitive tool list to the system prompt so the LLM can
    # accurately answer "what tools do you have?" from the actual registry.
    registered = registry.discover()
    logger.info(
        "[build_engine] session=%s | final registry (%d tools): %s",
        session_id, len(registered), [t.schema.name for t in registered],
    )
    if registered:
        tool_lines = [
            "",
            "## Your Executable Tools (Authoritative List)",
            "IMPORTANT: The following is the COMPLETE and ONLY list of callable tools",
            "available to you right now. Do NOT mention any tools not in this list.",
            "Do NOT list Skills as tools — Skills are workflow presets, not callable functions.",
            "",
        ]
        for t in registered:
            desc = (t.schema.description or "").split(".")[0]  # first sentence only
            tool_lines.append(f"- **{t.schema.name}**: {desc}")
        full_system = full_system + "\n" + "\n".join(tool_lines)

    overflow = OverflowStore()
    executor = ToolExecutor(
        registry=registry,
        overflow=overflow,
        emitter=emitter,
        limits=harness_cfg.tools.limits,
    )

    loop = ReactLoop(
        llm=llm,
        tool_registry=registry,
        tool_executor=executor,
        compressor=compressor,
        emitter=emitter,
        max_rounds=harness_cfg.engine.max_rounds,
    )

    return AgentEngine(
        config=EngineConfig(
            session_id=session_id,
            system_prompt=full_system,
            confirm_tools=frozenset(harness_cfg.tools.confirm_tools),
        ),
        loop=loop,
        session_store=session_store,
        emitter=emitter,
        tool_registry=registry,
    )


# ── MCP async helpers ────────────────────────────────────────────────────────

async def setup_mcp_servers(
    registry: ToolRegistry,
    harness_cfg: HarnessConfig,
) -> list:  # list[MCPClient]
    """Connect all MCP Servers declared in *harness_cfg* and register their
    tools into *registry*.

    Returns the list of connected MCPClient instances so the caller can
    ``await client.close()`` them on shutdown.

    Args:
        registry:    ToolRegistry to inject MCP tools into.
        harness_cfg: Config that may contain ``mcp_servers`` entries.

    Returns:
        List of active MCPClient instances (may be empty if none configured).
    """
    from harness.mcp.client import MCPClient
    from harness.mcp.bridge import register_mcp_server

    clients: list[MCPClient] = []
    for server_name, server_cfg in harness_cfg.mcp_servers.items():
        if server_cfg.transport != "stdio":
            logger.warning(
                "MCP Server '%s' uses unsupported transport '%s'; skipping.",
                server_name, server_cfg.transport,
            )
            continue
        if not server_cfg.command:
            logger.warning("MCP Server '%s' has no command; skipping.", server_name)
            continue

        client = MCPClient(server_name=server_name)
        try:
            await client.connect(server_cfg.command)
            registered = await register_mcp_server(registry, client, prefix=server_name)
            logger.info(
                "MCP Server '%s' connected; %d tool(s) registered: %s",
                server_name, len(registered), registered,
            )
            clients.append(client)
        except Exception as exc:
            logger.error(
                "Failed to connect MCP Server '%s': %s", server_name, exc
            )
            await client.close()

    return clients


async def build_engine_with_mcp(
    session_id: str,
    provider_cfg: ProviderConfig,
    harness_cfg: HarnessConfig,
    session_store: SessionStore,
    system_prompt: str = "",
    allowed_tools: list[str] | None = None,
) -> tuple[AgentEngine, list]:  # tuple[AgentEngine, list[MCPClient]]
    """Async variant of build_engine() that also initialises MCP Servers.

    Call this instead of ``build_engine()`` when ``mcp_servers`` are
    configured.  The returned MCPClient list must be closed by the caller::

        engine, mcp_clients = await build_engine_with_mcp(...)
        try:
            ...
        finally:
            for c in mcp_clients:
                await c.close()

    Args:
        session_id:    Unique session identifier.
        provider_cfg:  LLM provider config.
        harness_cfg:   Global harness config (may contain ``mcp_servers``).
        session_store: Session persistence backend.
        system_prompt: Base system prompt.
        allowed_tools: Persona-level tool whitelist.

    Returns:
        ``(engine, mcp_clients)`` tuple.
    """
    registry = ToolRegistry()
    mcp_clients = await setup_mcp_servers(registry, harness_cfg)

    engine = build_engine(
        session_id=session_id,
        provider_cfg=provider_cfg,
        harness_cfg=harness_cfg,
        session_store=session_store,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        registry=registry,
    )
    return engine, mcp_clients
