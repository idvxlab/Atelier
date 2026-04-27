"""
Engine factory — single source of truth for building an AgentEngine.

Both cli.py and api/rest.py import build_engine() from here.
To add a new tool, register it in ALL_TOOLS and add it to config.yaml tools.enabled.
"""
from __future__ import annotations

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
)
from harness.tools.executor import ToolExecutor
from harness.tools.overflow import OverflowStore
from harness.tools.registry import ToolRegistry

# Central tool registry — add new tools here only
ALL_TOOLS: dict[str, tuple] = {
    "read_file": (READ_FILE_SCHEMA, read_file_tool),
    "search":    (SEARCH_SCHEMA,    search_tool),
    "shell":     (SHELL_SCHEMA,     shell_tool),
}


def build_engine(
    session_id: str,
    provider_cfg: ProviderConfig,
    harness_cfg: HarnessConfig,
    session_store: SessionStore,
    system_prompt: str = "",
    allowed_tools: list[str] | None = None,
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

    registry = ToolRegistry()
    for name in tools_to_load:
        if name in ALL_TOOLS:
            schema, handler = ALL_TOOLS[name]
            registry.register(schema, handler)

    # use_skill is always available if skills exist (not controlled by allowed_tools)
    if skills:
        registry.register(USE_SKILL_SCHEMA, use_skill_tool)

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
        ),
        loop=loop,
        session_store=session_store,
        emitter=emitter,
    )
