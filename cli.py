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

from harness.config import HarnessConfig
from harness.engine.compression import CompressionConfig, ContextCompressor
from harness.engine.engine import AgentEngine, EngineConfig
from harness.engine.loop import ReactLoop
from harness.llm.registry import build_provider
from harness.observability.events import EventEmitter
from harness.skills import (
    load_persona, load_skill_content,
    list_skills, list_personas,
    build_skill_system_addendum,
)
from harness.storage.backends.memory import MemorySessionStore
from harness.tools.builtin import (
    READ_FILE_SCHEMA, read_file_tool,
    SEARCH_SCHEMA, search_tool,
    SHELL_SCHEMA, shell_tool,
    USE_SKILL_SCHEMA, use_skill_tool,
)
from harness.tools.executor import ToolExecutor
from harness.tools.overflow import OverflowStore
from harness.tools.registry import ToolRegistry
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


def _build_engine(cfg: HarnessConfig, provider_name: str,
                  system_prompt: str, session_id: str,
                  allowed_tools: list[str] | None = None) -> AgentEngine:
    provider_cfg = cfg.providers[provider_name]
    emitter = EventEmitter(session_id)
    llm = build_provider(provider_cfg)

    comp_cfg = cfg.compression
    if comp_cfg.summary_provider and comp_cfg.summary_provider in cfg.providers:
        summarizer = build_provider(cfg.providers[comp_cfg.summary_provider])
    else:
        summarizer = llm

    # Append skill descriptions so agent knows what skills are available
    skills = list_skills()
    full_system = system_prompt + build_skill_system_addendum(skills)

    compressor = ContextCompressor(
        summarizer=summarizer,
        config=CompressionConfig(
            token_window=comp_cfg.token_window,
            auto_trigger_ratio=comp_cfg.auto_trigger_ratio,
            micro_keep_recent=comp_cfg.micro_keep_recent,
            system_identity=full_system,
        ),
    )

    ALL_TOOLS = {
        "read_file": (READ_FILE_SCHEMA, read_file_tool),
        "search":    (SEARCH_SCHEMA,    search_tool),
        "shell":     (SHELL_SCHEMA,     shell_tool),
    }

    global_enabled = cfg.tools.enabled
    if allowed_tools is not None:
        if global_enabled is not None:
            tools_to_load = [t for t in allowed_tools if t in global_enabled]
        else:
            tools_to_load = allowed_tools
    else:
        tools_to_load = global_enabled if global_enabled is not None else list(ALL_TOOLS.keys())

    registry = ToolRegistry()
    for name in tools_to_load:
        if name in ALL_TOOLS:
            schema, handler = ALL_TOOLS[name]
            registry.register(schema, handler)
        else:
            print(_color(f"  ⚠  未知工具: {name}，已跳过", YELLOW))

    # use_skill always registered if skills exist
    if skills:
        registry.register(USE_SKILL_SCHEMA, use_skill_tool)

    overflow = OverflowStore()
    executor = ToolExecutor(
        registry=registry,
        overflow=overflow,
        emitter=emitter,
        limits=cfg.tools.limits,
    )

    loop = ReactLoop(
        llm=llm,
        tool_registry=registry,
        tool_executor=executor,
        compressor=compressor,
        emitter=emitter,
        max_rounds=cfg.engine.max_rounds,
    )
    return AgentEngine(
        config=EngineConfig(
            session_id=session_id,
            system_prompt=full_system,
        ),
        loop=loop,
        session_store=MemorySessionStore(),
        emitter=emitter,
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
    engine = _build_engine(cfg, provider_name, system_prompt, session_id,
                           allowed_tools=allowed_tools)
    prev_count = 0

    try:
        while True:
            try:
                user_input = input(_color("You > ", GREEN, BOLD)).strip()
            except EOFError:
                break

            if not user_input:
                continue

            # ── 内置命令 ───────────────────────────────────────────────
            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                print(_color("再见！", DIM))
                break

            if user_input.lower() == "/reset":
                session_id = str(uuid.uuid4())[:8]
                engine = _build_engine(cfg, provider_name, system_prompt, session_id,
                                       allowed_tools=allowed_tools)
                prev_count = 0
                print(_color(f"  [新会话已开启: {session_id}]", YELLOW))
                continue

            if user_input.lower() == "/tools":
                _TOOL_DESC = {
                    "read_file": "读取文件内容",
                    "search":    "正则搜索文件",
                    "shell":     "执行系统命令",
                    "use_skill": "加载 skill 说明",
                }
                active = allowed_tools if allowed_tools is not None else ["read_file", "search", "shell"]
                active_with_skill = active + ["use_skill"]
                print(_color("  可用工具：", CYAN))
                for t in active_with_skill:
                    desc = _TOOL_DESC.get(t, t)
                    print(f"    {t:<12} — {desc}")
                continue

            if user_input.lower() == "/state":
                snap = await engine.get_snapshot()
                print(_color(f"  状态: {snap['state']}  消息数: {len(snap['last_messages'])}", DIM))
                continue

            if user_input.lower() == "/skills":
                all_skills = list_skills()
                if not all_skills:
                    print(_color("  暂无可用 skill。新建: skills/<name>/SKILL.md", YELLOW))
                else:
                    print(_color("  可用 Skill（Agent 自动调用 / 用户手动 /<name>）：", CYAN))
                    for s in all_skills:
                        print(f"    {_color(s['name'], YELLOW):<28} {s['description']}")
                    print(_color("  新建: mkdir skills/<name> && 创建 SKILL.md", DIM))
                continue

            if user_input.lower() == "/personas":
                personas = list_personas()
                if not personas:
                    print(_color("  暂无可用 persona。新建: personas/<name>.md", YELLOW))
                else:
                    print(_color("  可用 Persona（用 --persona <name> 启动时选择）：", CYAN))
                    for p in personas:
                        desc = f" — {p['description']}" if p.get("description") else ""
                        print(f"    {_color(p['name'], YELLOW)}{desc}")
                continue

            # ── 手动调用 skill：/skill-name ────────────────────────────
            if user_input.startswith("/") and len(user_input) > 1:
                skill_name = user_input[1:].strip()
                try:
                    content = load_skill_content(skill_name)
                    # 把 skill 内容作为用户消息发送给引擎
                    skill_msg = (
                        f"[Skill '{skill_name}' manually invoked]\n\n"
                        f"{content}"
                    )
                    await engine.send_message(skill_msg)
                    prev_count = await _wait_for_completion(engine, prev_count)
                    print()
                except ValueError:
                    available = [s["name"] for s in list_skills()]
                    print(_color(f"  未知命令或 skill: '{skill_name}'", RED))
                    print(_color(f"  可用 skill: {', '.join(available)}", GRAY))
                continue

            # ── 发送消息 ───────────────────────────────────────────────
            await engine.send_message(user_input)
            prev_count = await _wait_for_completion(engine, prev_count)
            print()

    except KeyboardInterrupt:
        print(_color("\n\n  已中止。再见！", DIM))


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
