"""
Tests for harness/engine/prompt_cache.py.
"""
from __future__ import annotations

import pytest
from harness.engine.prompt_cache import PromptCache
from harness.types.tools import ToolSchema, ToolParam


# ── basic getter/setter ─────────────────────────────────────────────────

def test_cache_starts_empty():
    pc = PromptCache()
    assert pc.get_system_prompt() is None
    assert pc.get_tool_schemas() is None
    assert pc.get_mode_block("question") is None
    assert pc.get_mode_block("noquestion") is None


def test_set_and_get_system_prompt():
    pc = PromptCache()
    pc.set_system_prompt("Hello world")
    assert pc.get_system_prompt() == "Hello world"


def test_set_and_get_tool_schemas():
    pc = PromptCache()
    schemas = [
        ToolSchema(name="a", description="A", params=[]),
        ToolSchema(name="b", description="B", params=[]),
    ]
    pc.set_tool_schemas(schemas)
    cached = pc.get_tool_schemas()
    assert cached is schemas          # same object — no copy
    assert len(cached) == 2
    assert cached[0].name == "a"


def test_set_and_get_mode_blocks():
    pc = PromptCache()
    pc.set_mode_block("question", "Q block")
    pc.set_mode_block("noquestion", "NQ block")
    assert pc.get_mode_block("question") == "Q block"
    assert pc.get_mode_block("noquestion") == "NQ block"
    # Unknown mode
    assert pc.get_mode_block("other") is None


def test_invalidate_mode():
    pc = PromptCache()
    pc.set_mode_block("question", "Q")
    pc.set_mode_block("noquestion", "NQ")
    pc.invalidate_mode("question")
    assert pc.get_mode_block("question") is None
    assert pc.get_mode_block("noquestion") == "NQ"


def test_invalidate_all_modes():
    pc = PromptCache()
    pc.set_mode_block("question", "Q")
    pc.set_mode_block("noquestion", "NQ")
    pc.invalidate_all_modes()
    assert pc.get_mode_block("question") is None
    assert pc.get_mode_block("noquestion") is None


def test_refresh_tool_schemas():
    pc = PromptCache()
    schemas = [ToolSchema(name="x", description="X", params=[])]
    pc.set_tool_schemas(schemas)
    assert pc.get_tool_schemas() is schemas

    pc.refresh_tool_schemas()
    assert pc.get_tool_schemas() is None


def test_system_prompt_immutable_by_design():
    """
    The cache does not protect against the caller mutating the string,
    but it does guarantee the same object is returned every time —
    so the engine always gets the same reference without re-construction.
    """
    pc = PromptCache()
    pc.set_system_prompt("static base")
    # Repeated calls return the same object
    assert pc.get_system_prompt() is pc.get_system_prompt()
    assert pc.get_system_prompt() is pc.get_system_prompt()


def test_system_prompt_not_overwritten():
    """
    PromptCache has no set_system_prompt overwrite guard because the factory
    only calls it once per engine. The 'immutability' is by convention, not
    by enforcement — callers are responsible for calling it once.
    """
    pc = PromptCache()
    pc.set_system_prompt("first")
    pc.set_system_prompt("second")
    # By design, the second write wins (no overwrite protection needed).
    assert pc.get_system_prompt() == "second"
