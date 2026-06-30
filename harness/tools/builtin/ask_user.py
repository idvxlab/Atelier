"""
ask_user built-in tool — OpenCode / Claude Code style structured clarification.

Architecture (interrupt model, NOT blocking model):

  - This tool is **non-blocking**. It validates the LLM's input, registers a
    QuestionRequest on the engine, emits a `question.asked` event on the WS
    channel, and returns IMMEDIATELY with an InterruptibleToolResult carrying
    a placeholder string. It does NOT wait for the user.

  - The run loop detects the interruptible result (is_interrupt=True) and
    raises InterruptSignal. The engine catches it and transitions to
    WAITING_INTERRUPT. The conversation is left in a valid state:
    assistant(tool_call) → tool(placeholder). The user can now reply.

  - When the user submits answers (engine.submit_question_reply) or rejects
    (engine.reject_question), the engine:
      1. mutates the placeholder tool_result in `messages` to the real text;
      2. emits question.updated → question.resolved on the WS channel;
      3. transitions back to RUNNING and restarts the loop.

  - The tool never owns state, never blocks, and is replaced in spirit by
    the engine-level QuestionRequest lifecycle.

  - This tool is registered only when question_mode == "question".

  - The schema and lifecycle are documented in harness.types.questions and
    injected into the system prompt via factory._QUESTION_INSTRUCTIONS.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from harness.types.questions import (
    QuestionOption,
    QuestionPrompt,
    format_interrupt_placeholder,
)
from harness.types.tools import ToolSchema, ToolParam
from harness.tools.executor import InterruptibleToolResult

if TYPE_CHECKING:
    from harness.engine.engine import AgentEngine


ASK_USER_SCHEMA = ToolSchema(
    name="ask_user",
    description=(
        "Ask the user structured clarification questions and render them as a "
        "clickable UI (radio buttons for single-select, checkboxes for "
        "multi-select, with optional free-text input).\n\n"
        "WHEN TO USE:\n"
        "  - The user request is broad or ambiguous (e.g. 'design a website', "
        "'build me an app', 'write a project plan') and at least one critical "
        "constraint is missing.\n"
        "  - The user would clearly prefer to pick from options themselves.\n"
        "  - You need 2-5 distinct values from a known option set.\n\n"
        "WHEN NOT TO USE:\n"
        "  - The request is already concrete — just do the work.\n"
        "  - You can reasonably default unknown values — state the assumption.\n"
        "  - You've already asked once this turn (max one clarification round).\n\n"
        "HOW IT WORKS (interrupt model, NOT blocking):\n"
        "  1. You call this tool with structured questions. It returns "
        "IMMEDIATELY with a short placeholder.\n"
        "  2. The run loop pauses at the engine level.\n"
        "  3. The user sees an interactive question card and picks options.\n"
        "  4. The engine resumes the loop and feeds you the answers on the next "
        "round as a normal tool_result.\n"
        "  5. You then proceed with the actual task.\n\n"
        "STRICT RULES (violations break the UI):\n"
        "  - DO NOT ask clarification questions as plain assistant text. The "
        "frontend will not render markdown like '1. xxx  2. yyy' or 'A. xxx  "
        "B. xxx' as a clickable UI. Only a real tool call produces the UI.\n"
        "  - DO NOT write a preamble before calling this tool. If clarification "
        "is needed, your first response on that turn is the tool call.\n"
        "  - 1-5 questions per call. 2-5 options per question.\n"
        "  - Each option MUST have a short description (1-2 lines). For the "
        "recommended option, prefix its description with 'Recommended'.\n"
        "  - Set multiple=true for multi-select; multiple=false for single-select.\n"
        "  - Set custom=true to let the user type a free-text answer (replaces "
        "the legacy 'Other' option). Set custom=false to restrict to listed options.\n"
        "  - Mark options with their semantic intent in the description, not in "
        "the label. Labels are the user-visible button text.\n"
    ),
    params=[
        ToolParam(
            name="questions",
            type="array",
            description=(
                "REQUIRED. Array of 1-5 question prompts. Each prompt is an "
                "object with: question (string, the actual question text), "
                "header (string, short title shown above the question), "
                "options (array of 2-5 option objects, each with `label` and "
                "`description`), multiple (boolean, allow multi-select), "
                "custom (boolean, allow free-text answer not in options)."
            ),
            items={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": (
                            "The full question text shown to the user, e.g. "
                            "'网站的主要用途是什么？'. Must be a complete question, "
                            "not a one-word prompt."
                        ),
                    },
                    "header": {
                        "type": "string",
                        "description": (
                            "Short title (1-4 words) shown above the question "
                            "as a section label, e.g. '网站目标', '目标用户'. "
                            "Optional but strongly recommended for multi-question cards."
                        ),
                    },
                    "options": {
                        "type": "array",
                        "description": (
                            "Array of 2-5 option objects. Each option is a "
                            "clickable choice. REQUIRED: at least 2 options."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {
                                    "type": "string",
                                    "description": (
                                        "The user-visible button text. Should be "
                                        "short (1-6 words) and self-explanatory. "
                                        "e.g. '展示公司信息', '销售产品'."
                                    ),
                                },
                                "description": {
                                    "type": "string",
                                    "description": (
                                        "1-2 line description of what this option "
                                        "means. Prefix with 'Recommended' for the "
                                        "best default. e.g. '适合企业官网、品牌介绍 · "
                                        "Recommended'."
                                    ),
                                },
                            },
                            "required": ["label", "description"],
                        },
                    },
                    "multiple": {
                        "type": "boolean",
                        "description": (
                            "false = single-select (radio). true = multi-select "
                            "(checkboxes). Default false."
                        ),
                    },
                    "custom": {
                        "type": "boolean",
                        "description": (
                            "true = show a free-text input so the user can type "
                            "an answer not in the options list. false = restrict "
                            "to the listed options only. Default true."
                        ),
                    },
                },
                "required": ["question", "options"],
            },
        ),
    ],
)


def _normalize_questions(raw_questions) -> list[QuestionPrompt]:
    """
    Validate and normalize the questions list from the LLM, returning a
    clean list of QuestionPrompt objects. Raises ValueError on invalid input.
    """
    if not isinstance(raw_questions, list):
        raise ValueError("`questions` must be a list")
    if len(raw_questions) < 1:
        raise ValueError("`questions` must contain at least 1 question")
    if len(raw_questions) > 5:
        raise ValueError("`questions` cannot exceed 5 questions (max 5)")

    out: list[QuestionPrompt] = []
    for idx, q in enumerate(raw_questions):
        if not isinstance(q, dict):
            raise ValueError(f"questions[{idx}] must be an object")

        question_text = (q.get("question") or "").strip()
        if not question_text:
            raise ValueError(f"questions[{idx}].question must be non-empty")

        raw_opts = q.get("options") or []
        if not isinstance(raw_opts, list):
            raise ValueError(f"questions[{idx}].options must be a list")
        if len(raw_opts) < 2:
            raise ValueError(
                f"questions[{idx}] needs at least 2 options, got {len(raw_opts)}"
            )
        if len(raw_opts) > 5:
            raw_opts = raw_opts[:5]

        options: list[QuestionOption] = []
        seen_labels: set[str] = set()
        for o in raw_opts:
            if not isinstance(o, dict):
                raise ValueError(f"questions[{idx}].options entries must be objects")
            label = (o.get("label") or "").strip()
            if not label:
                raise ValueError(
                    f"questions[{idx}] option missing non-empty label"
                )
            if label in seen_labels:
                continue
            seen_labels.add(label)
            options.append(
                QuestionOption(
                    label=label,
                    description=(o.get("description") or "").strip() or None,
                )
            )

        if len(options) < 2:
            raise ValueError(
                f"questions[{idx}] needs at least 2 distinct labels"
            )

        out.append(
            QuestionPrompt(
                question=question_text,
                header=(q.get("header") or "").strip() or None,
                options=options,
                multiple=bool(q.get("multiple", False)),
                custom=bool(q.get("custom", False)),
            )
        )

    return out


def make_ask_user_tool(engine: "AgentEngine"):
    """
    Return an ask_user handler closed over the given engine.

    The handler is intentionally non-blocking: it validates input, registers
    a QuestionRequest, and returns an InterruptibleToolResult. The run loop
    detects the interrupt flag, the engine pauses, and a later reply via
    engine.submit_question_reply() / reject_question() resumes the loop.
    """

    async def ask_user_tool(questions: list, _tool_call_id: str = "") -> InterruptibleToolResult | str:
        try:
            prompts = _normalize_questions(questions)
        except ValueError as exc:
            # Validation failures are NOT interrupts — return a plain error
            # so the LLM can self-correct on the next round.
            return f"Error: ask_user rejected input: {exc}"

        # The executor threads the LLM-generated tool_call_id as a reserved
        # kwarg. We MUST use this id (not a fresh uuid) so the placeholder
        # tool_result block satisfies the assistant→tool message pair
        # invariant (validate_message_sequence).
        if not _tool_call_id:
            # Should never happen — executor always passes this kwarg.
            return "Error: ask_user missing tool_call_id from executor"
        request_id = str(uuid.uuid4())

        # Engine is the single source of truth. This call:
        #   - inserts the request into _pending_question_requests
        #   - emits question.asked on the WS channel
        #   - notifies state listeners
        await engine.register_question_request(
            request_id=request_id,
            tool_call_id=_tool_call_id,
            questions=prompts,
        )

        # Return IMMEDIATELY. The loop sees is_interrupt=True and raises
        # InterruptSignal; the engine catches it and parks in WAITING_INTERRUPT.
        return InterruptibleToolResult(
            content=format_interrupt_placeholder(request_id),
        )

    return ask_user_tool
