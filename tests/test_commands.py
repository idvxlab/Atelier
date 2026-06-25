"""Unit tests for the command system."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.commands.models import (
    Command,
    CommandResult,
    CommandContext,
    PARAM_PATTERN,
    substitute_args,
    extract_params,
    serialize_command,
)
from harness.commands.registry import CommandRegistry
from harness.commands.builtin import make_builtin_commands
from harness.commands.loader import (
    load_custom_commands,
    _load_from_dir,
    _parse_command_file,
    _make_custom_handler,
)
from harness.commands import CommandSystem


# ── PARAM_PATTERN ────────────────────────────────────────────────────────────


class TestParamPattern:
    def test_matches_valid_params(self):
        assert PARAM_PATTERN.findall("Hello $NAME") == ["NAME"]
        assert PARAM_PATTERN.findall("$ISSUE_NUMBER and $BRANCH_NAME") == [
            "ISSUE_NUMBER",
            "BRANCH_NAME",
        ]
        assert PARAM_PATTERN.findall("$TARGET_ENV") == ["TARGET_ENV"]

    def test_rejects_lowercase(self):
        assert PARAM_PATTERN.findall("$foo") == []

    def test_rejects_leading_digit(self):
        assert PARAM_PATTERN.findall("$1FOO") == []

    def test_rejects_leading_underscore(self):
        assert PARAM_PATTERN.findall("$_FOO") == []


class TestExtractParams:
    def test_returns_deduplicated_list(self):
        content = "Fix issue #$ISSUE_NUMBER in branch $ISSUE_NUMBER"
        assert extract_params(content) == ["ISSUE_NUMBER"]

    def test_returns_empty_for_no_params(self):
        assert extract_params("Just a plain prompt") == []

    def test_preserves_order(self):
        content = "$A $B $A $C"
        assert extract_params(content) == ["A", "B", "C"]


class TestSubstituteArgs:
    def test_replaces_all_occurrences(self):
        content = "Fix $BUG in $BUG branch"
        result = substitute_args(content, {"BUG": "123"})
        assert result == "Fix 123 in 123 branch"

    def test_leaves_unknown_vars_intact(self):
        result = substitute_args("Hello $NAME", {})
        assert result == "Hello $NAME"


# ── Serialization ────────────────────────────────────────────────────────────


class TestSerializeCommand:
    def test_serializes_all_fields(self):
        cmd = Command(
            id="test:my-cmd",
            title="My Command",
            description="Does things",
            source="project",
            params=["FOO"],
        )
        d = serialize_command(cmd)
        assert d["id"] == "test:my-cmd"
        assert d["title"] == "My Command"
        assert d["description"] == "Does things"
        assert d["source"] == "project"
        assert d["has_params"] is True
        assert d["params"] == ["FOO"]

    def test_has_params_false_when_empty(self):
        cmd = Command(id="x", title="X")
        assert serialize_command(cmd)["has_params"] is False


# ── CommandRegistry ──────────────────────────────────────────────────────────


class TestCommandRegistry:
    def test_register_and_discover(self):
        reg = CommandRegistry()
        reg.register(Command(id="a", title="A"))
        reg.register(Command(id="b", title="B"))
        assert len(reg.discover()) == 2

    def test_resolve_by_full_id(self):
        reg = CommandRegistry()
        reg.register(Command(id="project:github:issue", title="GH Issue"))
        assert reg.resolve("project:github:issue") is not None

    def test_resolve_by_short_name(self):
        reg = CommandRegistry()
        reg.register(Command(id="project:github:issue", title="GH Issue"))
        cmd = reg.resolve("issue")
        assert cmd is not None
        assert cmd.id == "project:github:issue"

    def test_resolve_not_found(self):
        reg = CommandRegistry()
        assert reg.resolve("nonexistent") is None

    def test_resolve_short_name_ambiguity_picks_first(self):
        reg = CommandRegistry()
        reg.register(Command(id="project:a:review", title="R1"))
        reg.register(Command(id="project:b:review", title="R2"))
        # First registered wins
        assert reg.resolve("review").id == "project:a:review"

    def test_unregister(self):
        reg = CommandRegistry()
        reg.register(Command(id="x", title="X"))
        reg.unregister("x")
        assert reg.get("x") is None

    def test_get_exact_only(self):
        reg = CommandRegistry()
        reg.register(Command(id="project:x", title="X"))
        assert reg.get("x") is None
        assert reg.get("project:x") is not None


# ── Built-in Commands ────────────────────────────────────────────────────────


class TestBuiltinCommands:
    @pytest.fixture
    def ctx(self):
        return CommandContext()

    @pytest.fixture
    def cmds(self):
        return {c.id: c for c in make_builtin_commands()}

    def test_all_nine_registered(self, cmds):
        expected = {"help", "init", "compact", "tools", "skills",
                     "personas", "state", "exit", "skill-install"}
        assert set(cmds.keys()) == expected

    def test_help_is_internal(self, cmds, ctx):
        r = cmds["help"].handler(cmds["help"], ctx)
        assert r.kind == "internal"
        assert r.action == "help"

    def test_init_is_prompt(self, cmds, ctx):
        r = cmds["init"].handler(cmds["init"], ctx)
        assert r.kind == "prompt"
        assert "MYHARNESS.md" in r.prompt_text

    def test_compact_is_prompt(self, cmds, ctx):
        r = cmds["compact"].handler(cmds["compact"], ctx)
        assert r.kind == "prompt"
        assert "summary" in r.prompt_text.lower()

    def test_tools_skills_personas_state_are_internal(self, cmds, ctx):
        for cid in ("tools", "skills", "personas", "state"):
            r = cmds[cid].handler(cmds[cid], ctx)
            assert r.kind == "internal"

    def test_exit_is_internal(self, cmds, ctx):
        r = cmds["exit"].handler(cmds["exit"], ctx)
        assert r.kind == "internal"
        assert r.action == "exit"


# ── Custom Command Loader ────────────────────────────────────────────────────


class TestCustomHandler:
    def test_returns_prompt_when_no_params(self):
        handler = _make_custom_handler("Plain prompt")
        cmd = Command(id="x", title="X")
        result = handler(cmd, CommandContext())
        assert result.kind == "prompt"
        assert result.prompt_text == "Plain prompt"

    def test_returns_needs_args_when_params_present(self):
        handler = _make_custom_handler("Fix issue #$ISSUE_NUMBER")
        cmd = Command(id="x", title="X")
        result = handler(cmd, CommandContext())
        assert result.kind == "needs-args"
        assert result.args_needed == ["ISSUE_NUMBER"]
        assert result.raw_content == "Fix issue #$ISSUE_NUMBER"


class TestParseCommandFile:
    def test_with_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(
            "---\n"
            "title: My Command\n"
            "description: Does stuff\n"
            "---\n"
            "Please do $THING\n",
            encoding="utf-8",
        )
        cmd = _parse_command_file(f, "project:test")
        assert cmd.id == "project:test"
        assert cmd.title == "My Command"
        assert cmd.description == "Does stuff"
        assert cmd.raw_content == "Please do $THING"
        assert cmd.params == ["THING"]

    def test_without_frontmatter(self, tmp_path):
        f = tmp_path / "plain.md"
        f.write_text("Just a prompt", encoding="utf-8")
        cmd = _parse_command_file(f, "project:plain")
        assert cmd.title == "Plain"
        assert cmd.raw_content == "Just a prompt"
        assert cmd.params == []

    def test_frontmatter_overrides_id(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(
            "---\n"
            "name: my-alias\n"
            "---\n"
            "Some content\n",
            encoding="utf-8",
        )
        cmd = _parse_command_file(f, "project:test")
        assert cmd.id == "my-alias"


class TestLoadFromDir:
    def test_flat_structure(self, tmp_path):
        (tmp_path / "deploy.md").write_text("Deploy to $ENV", encoding="utf-8")
        (tmp_path / "review.md").write_text("Review changes", encoding="utf-8")
        cmds = _load_from_dir(tmp_path, prefix="project")
        assert len(cmds) == 2
        ids = {c.id for c in cmds}
        assert ids == {"project:deploy", "project:review"}

    def test_nested_structure(self, tmp_path):
        gh = tmp_path / "github"
        gh.mkdir()
        (gh / "issue.md").write_text("Fix $ISSUE_NUMBER", encoding="utf-8")
        cmds = _load_from_dir(tmp_path, prefix="project")
        ids = {c.id for c in cmds}
        assert ids == {"project:github:issue"}

    def test_empty_dir(self, tmp_path):
        cmds = _load_from_dir(tmp_path, prefix="project")
        assert cmds == []

    def test_non_existent_dir(self, tmp_path):
        cmds = _load_from_dir(tmp_path / "nope", prefix="project")
        assert cmds == []


# ── CommandSystem ────────────────────────────────────────────────────────────


class TestCommandSystem:
    def test_initialize_registers_builtins(self):
        cs = CommandSystem()
        cs.initialize()
        assert cs.resolve("help") is not None
        assert cs.resolve("init") is not None
        assert cs.resolve("exit") is not None

    def test_initialize_is_idempotent(self):
        cs = CommandSystem()
        cs.initialize()
        count = len(cs.discover())
        cs.initialize()
        assert len(cs.discover()) == count

    def test_list_all_returns_json_safe(self):
        cs = CommandSystem()
        cs.initialize()
        entries = cs.list_all()
        assert isinstance(entries, list)
        assert all(isinstance(e, dict) for e in entries)
        assert "id" in entries[0]
        assert "title" in entries[0]
        assert "source" in entries[0]

    def test_resolve_short_name_works(self):
        cs = CommandSystem()
        cs.initialize()
        cmd = cs.resolve("help")
        assert cmd is not None
        assert cmd.id == "help"

    def test_idempotent_initialization(self):
        cs = CommandSystem()
        cs.initialize()
        n1 = len(cs.discover())
        cs.initialize()
        n2 = len(cs.discover())
        assert n1 == n2
