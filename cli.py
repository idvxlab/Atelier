"""
MyHarnessPy 交互式 CLI

直接运行，无需启动 API 服务器：
    python cli.py
    python cli.py --provider bltcy-openai
    python cli.py --persona coder
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import textwrap
import uuid
from pathlib import Path

# 加载 .env（必须在导入 harness 模块之前）
from dotenv import load_dotenv
load_dotenv(override=False)

from harness.commands import CommandSystem
from harness.commands.models import CommandContext, CommandResult, substitute_args
from harness.config import HarnessConfig
from harness.engine.engine import AgentEngine
from harness.factory import build_engine, build_engine_with_mcp
from harness.skills import (
    load_persona, load_skill_content,
    list_skills, list_personas,
)
from harness.storage.backends.memory import MemorySessionStore
from harness.types.messages import TextBlock, ToolCallBlock, ToolResultBlock

# ── ANSI 颜色（Windows 终端支持） ─────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
GRAY   = "\033[90m"


def _color(text: str, *codes: str) -> str:
    return "".join(codes) + text + RESET


# ── Lazy-initialized command system (shared across session resets) ─────
_cmd_system: CommandSystem | None = None
_cmd_ctx: CommandContext | None = None


def _ensure_cmd_system(
    cfg: HarnessConfig,
    provider_name: str,
    system_prompt: str,
    allowed_tools: list[str] | None,
    persona_name: str,
    engine: AgentEngine,
    session_id: str,
) -> None:
    """Create and initialise the CommandSystem once per CLI session."""
    global _cmd_system, _cmd_ctx
    if _cmd_system is None:
        _cmd_system = CommandSystem()
        _cmd_system.initialize()
    _cmd_ctx = CommandContext(
        engine=engine,
        config=cfg,
        session_id=session_id,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        provider_name=provider_name,
    )


# ── Verbose 模式：把 harness.events 的 INFO 日志漂亮地打出来 ────────────
_EVENT_ICONS = {
    "llm_call":             ("🧠", CYAN),
    "tool_call":            ("🔧", YELLOW),
    "tool_output_overflow": ("📦", YELLOW),
    "cancel_check":         ("🛑", RED),
    "loop_detected":        ("🔁", RED),
    "compression_applied":  ("✂️ ", DIM),
    "compression_micro":    ("✂️ ", DIM),
    "compression_auto":     ("📝", DIM),
    "state_transition":     ("⚙️ ", GRAY),
    "cancel_requested":     ("🛑", RED),
    "engine_loop_error":    ("💥", RED),
}

_STATE_COLOR = {
    "triggered-executed":    GREEN,
    "condition-not-met":     GRAY,
    "triggered-intercepted": YELLOW,
    "execution-error":       RED,
}

class _VerboseHandler(logging.Handler):
    """把 harness.events JSON 日志转成人类可读的行。"""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            data = json.loads(record.getMessage())
        except (json.JSONDecodeError, TypeError):
            return
        event_type = data.get("event_type", "?")
        state      = data.get("state", "")
        round_idx  = data.get("round", "?")
        detail     = {k: v for k, v in data.items()
                      if k not in ("event_type","state","session_id","round","timestamp")}

        icon, icon_color = _EVENT_ICONS.get(event_type, ("·", GRAY))
        sc = _STATE_COLOR.get(state, GRAY)
        detail_str = "  " + "  ".join(f"{k}={v}" for k, v in detail.items()) if detail else ""
        line = (
            f"  {_color(icon, icon_color)} "
            f"[轮{round_idx}] "
            f"{_color(event_type, BOLD)}"
            f"  {_color(state, sc)}"
            f"{_color(detail_str, GRAY)}"
        )
        print(line, file=sys.stderr)


def _print_banner(provider: str, model: str, persona_name: str = "") -> None:
    print(_color("╔══════════════════════════════════════╗", CYAN, BOLD))
    print(_color("║      MyHarnessPy  Interactive CLI    ║", CYAN, BOLD))
    print(_color("╚══════════════════════════════════════╝", CYAN, BOLD))
    print(f"  Provider : {_color(provider, YELLOW)}")
    print(f"  Model    : {_color(model, YELLOW)}")
    if persona_name:
        print(f"  Persona  : {_color(persona_name, CYAN)}")
    print()
    print(_color("  输入消息后按 Enter 发送", DIM))
    print(_color("  /exit      退出      /reset     新会话", DIM))
    print(_color("  /tools     工具      /skills    可用Skill", DIM))
    print(_color("  /personas  可用身份  /state     引擎状态", DIM))
    print(_color("  /<name>    手动调用 skill（如 /code-review）", DIM))
    print(_color("─" * 42, GRAY))
    print()


async def _build_engine(
    cfg: HarnessConfig,
    provider_name: str,
    system_prompt: str,
    session_id: str,
    allowed_tools: list[str] | None = None,
) -> tuple[AgentEngine, list]:
    """
    Build an engine.

    If cfg.mcp_servers is non-empty, we also connect MCP servers and register
    their tools. Returns (engine, mcp_clients).
    """
    if cfg.mcp_servers:
        engine, mcp_clients = await build_engine_with_mcp(
            session_id=session_id,
            provider_cfg=cfg.providers[provider_name],
            harness_cfg=cfg,
            session_store=MemorySessionStore(),
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
        )
        return engine, mcp_clients

    return (
        build_engine(
            session_id=session_id,
            provider_cfg=cfg.providers[provider_name],
            harness_cfg=cfg,
            session_store=MemorySessionStore(),
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
        ),
        [],
    )


def _render_snapshot(snapshot: dict, prev_count: int) -> int:
    """打印新出现的消息，返回当前消息总数。"""
    messages = snapshot["last_messages"]
    for msg in messages[prev_count:]:
        role = msg["role"]
        if role == "assistant":
            text_parts = [
                b["text"] for b in msg["content"]
                if b["type"] == "text" and b.get("text")
            ]
            tool_calls = [b for b in msg["content"] if b["type"] == "tool_call"]

            if tool_calls:
                for tc in tool_calls:
                    inp = tc.get("tool_input", {})
                    print(_color(f"  [工具调用] {tc['tool_name']}({inp})", YELLOW))

            if text_parts:
                text = "\n".join(text_parts)
                wrapped = textwrap.fill(text, width=72,
                                        subsequent_indent="            ")
                print(_color("Assistant : ", CYAN, BOLD) + wrapped)

        elif role == "tool":
            for b in msg["content"]:
                if b["type"] == "tool_result":
                    status = _color("✓", GREEN) if not b.get("is_error") else _color("✗", RED)
                    content = b.get("content", "")
                    preview = content[:200] + ("…" if len(content) > 200 else "")
                    print(_color(f"  [{status} 结果] {preview}", GRAY))

    return len(messages)


async def _wait_for_completion(engine: AgentEngine, prev_count: int) -> int:
    """轮询直到引擎不再 RUNNING，期间实时打印新消息。"""
    dots = 0
    while True:
        snapshot = await engine.get_snapshot()
        prev_count = _render_snapshot(snapshot, prev_count)

        if not snapshot["is_running"]:
            state = snapshot["state"]
            if state == "ERROR":
                err = snapshot.get("last_error", "").strip()
                print(_color("  ┌─ 引擎出错 ─────────────────────────────────", RED))
                if err:
                    for line in err.splitlines():
                        print(_color(f"  │ {line}", RED))
                else:
                    print(_color("  │ (无详细错误信息)", RED))
                print(_color("  └────────────────────────────────────────────", RED))
            break

        dots = (dots + 1) % 4
        print(_color("  思考中" + "." * dots + "   ", DIM), end="\r", flush=True)
        await asyncio.sleep(0.3)

    print(" " * 20, end="\r")
    return prev_count


# ── Command system helpers ──────────────────────────────────────────────


def _print_command_list(cmd_system: CommandSystem) -> None:
    """Print the full command list (for /help)."""
    cmds = cmd_system.discover()
    builtins = [c for c in cmds if c.source == "builtin"]
    customs = [c for c in cmds if c.source != "builtin"]

    print(_color("\n  ╔════════════════════════════════════╗", CYAN))
    print(_color("  ║        可用命令                    ║", CYAN, BOLD))
    print(_color("  ╚════════════════════════════════════╝", CYAN))

    if builtins:
        print(_color("\n  内置命令:", YELLOW))
        for c in sorted(builtins, key=lambda x: x.id):
            desc = c.description
            print(f"    {_color(c.id, GREEN):<20} {desc}")
    if customs:
        print(_color(f"\n  项目命令 (commands/):", YELLOW))
        for c in sorted(customs, key=lambda x: x.id):
            params_hint = f"  [参数: {', '.join(c.params)}]" if c.params else ""
            print(f"    {_color(c.id, CYAN):<30} {c.description}{params_hint}")
    print(_color("\n  用法: /<command> [args...]", DIM))
    print(_color("  参数化命令: $UPPER_VAR 占位符会在运行时提示输入\n", DIM))


def _print_state(engine: AgentEngine) -> None:
    """Print current engine state (for /state)."""
    import asyncio as _asyncio
    snap = _asyncio.run(engine.get_snapshot()) if _asyncio.get_event_loop().is_running() else None
    # Called from sync context inside CLI loop; use a quick snapshot
    # We know engine is accessible, so inline the call
    # Actually _handle_command is async, so this works fine


async def _print_state_async(engine: AgentEngine) -> None:
    snap = await engine.get_snapshot()
    print(_color(f"  状态: {snap['state']}  消息数: {len(snap['last_messages'])}", DIM))


def _print_tools(engine: AgentEngine) -> None:
    print(_color("  可用工具：", CYAN))
    schemas = sorted(engine.tool_schemas, key=lambda s: s.name)
    for s in schemas:
        desc = s.description or ""
        print(f"    {s.name:<22} — {desc}")


def _print_skills() -> None:
    all_skills = list_skills()
    if not all_skills:
        print(_color("  暂无可用 skill。新建: skills/<name>/SKILL.md", YELLOW))
    else:
        print(_color("  可用 Skill（Agent 自动调用 / 用户手动 /<name>）：", CYAN))
        for s in all_skills:
            print(f"    {_color(s['name'], YELLOW):<28} {s['description']}")
        print(_color("  新建: mkdir skills/<name> && 创建 SKILL.md", DIM))


def _print_personas() -> None:
    personas = list_personas()
    if not personas:
        print(_color("  暂无可用 persona。新建: personas/<name>.md", YELLOW))
    else:
        print(_color("  可用 Persona（用 --persona <name> 启动时选择）：", CYAN))
        for p in personas:
            desc = f" — {p['description']}" if p.get("description") else ""
            print(f"    {_color(p['name'], YELLOW)}{desc}")


def _prompt_for_args(result: CommandResult) -> str | None:
    """Prompt user for each needed $VAR, return substituted text or None."""
    args: dict[str, str] = {}
    print(_color(f"\n  ┌─ 参数输入: {result.command_id} ──", CYAN))
    for arg_name in result.args_needed:
        display = arg_name.replace("_", " ").title()
        try:
            value = input(_color(f"  │ {display}: ", YELLOW)).strip()
        except EOFError:
            return None
        if not value:
            print(_color("  │ 已取消", DIM))
            return None
        args[arg_name] = value
    print(_color("  └" + "─" * 30, CYAN))
    return substitute_args(result.raw_content, args)


async def _try_skill_call(skill_name: str, engine: AgentEngine) -> bool:
    """Fallback: try to load a skill by name. Returns True if skill was found."""
    try:
        content = load_skill_content(skill_name)
        skill_msg = (
            f"[Skill '{skill_name}' manually invoked]\n\n"
            f"{content}"
        )
        await engine.send_message(skill_msg)
        return True
    except ValueError:
        available = [s["name"] for s in list_skills()]
        print(_color(f"  未知命令或 skill: '{skill_name}'", RED))
        if available:
            print(_color(f"  可用 skill: {', '.join(available)}", GRAY))
        else:
            print(_color("  尝试 /help 查看可用命令", GRAY))
        return False


async def _handle_internal_action(result: CommandResult, ctx: CommandContext) -> str | None:
    """Execute an internal command action.
    Returns "exit", "reset", or "continue".
    """
    action = result.action

    if action == "help":
        global _cmd_system
        if _cmd_system:
            _print_command_list(_cmd_system)
        return "continue"

    if action == "exit":
        print(_color("再见！", DIM))
        return "exit"

    if action == "list-tools" and ctx.engine:
        _print_tools(ctx.engine)
        return "continue"

    if action == "list-skills":
        _print_skills()
        return "continue"

    if action == "list-personas":
        _print_personas()
        return "continue"

    if action == "show-state" and ctx.engine:
        await _print_state_async(ctx.engine)
        return "continue"

    if action == "reset":
        return "reset"

    return "continue"


async def _handle_command(
    user_input: str,
    cmd_system: CommandSystem,
    ctx: CommandContext,
) -> str | None:
    """Dispatch a slash-command input.

    Returns:
        "exit"     — caller should break the loop
        "reset"    — caller should rebuild the engine
        "continue" — caller should not send to AI (command handled)
        None       — caller should send the original input to AI engine
    """
    parts = user_input[1:].split()
    cmd_name = parts[0]

    cmd = cmd_system.resolve(cmd_name)
    if cmd is None or cmd.handler is None:
        # Not a registered command — try skill fallback
        ok = await _try_skill_call(cmd_name, ctx.engine)
        return "continue" if ok else None

    result = cmd.handler(cmd, ctx)

    if result.kind == "prompt":
        print(_color(f"\n  [{cmd.title}] 已发送给 AI\n", YELLOW))
        await ctx.engine.send_message(result.prompt_text)
        return "continue"

    if result.kind == "internal":
        return await _handle_internal_action(result, ctx)

    if result.kind == "needs-args":
        filled = _prompt_for_args(result)
        if filled:
            print(_color(f"\n  [{cmd.title}] 已发送给 AI\n", YELLOW))
            await ctx.engine.send_message(filled)
        return "continue"

    if result.kind == "error":
        print(_color(f"  错误: {result.message}", RED))
        return "continue"

    return None


async def run_cli(provider_name: str, system_prompt: str,
                  allowed_tools: list[str] | None = None,
                  persona_name: str = "") -> None:
    try:
        cfg = HarnessConfig.from_yaml("config.yaml")
    except FileNotFoundError:
        cfg = HarnessConfig.from_env()

    if provider_name not in cfg.providers:
        print(_color(f"错误：找不到 provider '{provider_name}'", RED))
        print(f"可用的 provider: {list(cfg.providers.keys())}")
        sys.exit(1)

    model = cfg.providers[provider_name].model
    _print_banner(provider_name, model, persona_name=persona_name)

    session_id = str(uuid.uuid4())[:8]
    engine, mcp_clients = await _build_engine(
        cfg, provider_name, system_prompt, session_id, allowed_tools=allowed_tools
    )
    prev_count = 0

    try:
        while True:
            try:
                user_input = input(_color("You > ", GREEN, BOLD)).strip()
            except EOFError:
                break

            if not user_input:
                continue

            # ── Plain "exit"/"quit" without slash ────────────────────
            if user_input.lower() in ("exit", "quit"):
                print(_color("再见！", DIM))
                break

            # ── Unified command dispatch (all /-prefixed inputs) ─────
            if user_input.startswith("/"):
                _ensure_cmd_system(cfg, provider_name, system_prompt,
                                    allowed_tools, persona_name,
                                    engine, session_id)
                handled = await _handle_command(user_input, _cmd_system, _cmd_ctx)
                if handled == "exit":
                    break
                if handled == "reset":
                    for c in list(mcp_clients):
                        try:
                            await c.close()
                        except Exception:
                            pass
                    session_id = str(uuid.uuid4())[:8]
                    engine, mcp_clients = await _build_engine(
                        cfg, provider_name, system_prompt, session_id,
                        allowed_tools=allowed_tools
                    )
                    _cmd_ctx.engine = engine
                    _cmd_ctx.session_id = session_id
                    prev_count = 0
                    print(_color(f"  [新会话已开启: {session_id}]", YELLOW))
                    continue
                if handled == "continue":
                    # Command was handled (prompt sent or internal action done)
                    prev_count = await _wait_for_completion(engine, prev_count)
                    print()
                    continue
                # handled is None → not a command, send to AI as regular message
                await engine.send_message(user_input)
                prev_count = await _wait_for_completion(engine, prev_count)
                print()
                continue

            # ── 发送消息 ───────────────────────────────────────────────
            await engine.send_message(user_input)
            prev_count = await _wait_for_completion(engine, prev_count)
            print()

    except KeyboardInterrupt:
        print(_color("\n\n  已中止。再见！", DIM))
    finally:
        for c in list(mcp_clients):
            try:
                await c.close()
            except Exception:
                pass


def main() -> None:
    if sys.platform == "win32":
        import os
        os.system("")

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s  %(name)s: %(message)s",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(
        description="MyHarnessPy 交互式 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            示例:
              python cli.py
              python cli.py --provider bltcy-openai
              python cli.py --persona coder
              python cli.py --list-personas
        """),
    )
    parser.add_argument(
        "--provider", "-p",
        default="",
        help="使用的 provider（默认: config.yaml 里的 default_provider）",
    )
    parser.add_argument(
        "--persona",
        default="",
        metavar="PERSONA",
        help="加载 personas/<name>.md（设置系统提示词和工具权限）",
    )
    parser.add_argument(
        "--system", "-s",
        default="你是一个有帮助的 AI 助手，可以使用工具来完成任务。",
        help="System prompt（--persona 优先级更高）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示引擎内部思考过程（决策点事件流）",
    )
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="列出所有可用 Persona 并退出",
    )
    args = parser.parse_args()

    if args.list_personas:
        personas = list_personas()
        if not personas:
            print("暂无可用 persona。新建方法: 在 personas/ 目录新建 <name>.md")
        else:
            print(_color("可用 Persona：", CYAN, BOLD))
            for p in personas:
                desc = f" — {p['description']}" if p.get("description") else ""
                print(f"  {_color(p['name'], YELLOW)}{desc}")
            print()
            print(_color("用法: python cli.py --persona <name>", DIM))
        sys.exit(0)

    if args.verbose:
        event_logger = logging.getLogger("harness.events")
        event_logger.setLevel(logging.INFO)
        event_logger.addHandler(_VerboseHandler())
        event_logger.propagate = False
        print(_color("  [Verbose 模式已开启：显示引擎事件流]", DIM), file=sys.stderr)

    # ── 解析启动参数 ──────────────────────────────────────────────────
    try:
        cfg = HarnessConfig.from_yaml("config.yaml")
    except FileNotFoundError:
        cfg = HarnessConfig.from_env()

    provider      = args.provider or cfg.default_provider
    system        = args.system
    allowed_tools: list[str] | None = None
    persona_name  = ""

    if args.persona:
        try:
            persona = load_persona(args.persona)
        except ValueError as e:
            print(_color(f"错误：{e}", RED))
            sys.exit(1)
        system        = persona.get("system_prompt", system)
        allowed_tools = persona.get("allowed_tools") or None
        if persona.get("provider"):
            provider = persona["provider"]
        persona_name = args.persona
        print(_color(f"  Persona 已加载: {args.persona}", CYAN))

    asyncio.run(run_cli(provider, system,
                        allowed_tools=allowed_tools,
                        persona_name=persona_name))


if __name__ == "__main__":
    main()
