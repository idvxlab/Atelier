"""
Shared types for the Question Mode (OpenCode/Claude Code style).

These types are the single source of truth for:
  - ask_user tool input  (list[QuestionPrompt])
  - ask_user tool output (QuestionToolResult — non-blocking placeholder)
  - QuestionRequest storage in the engine
  - REST API request/response shapes
  - WebSocket event payloads (question.asked / updated / resolved)

Architecture invariants (must be preserved across the codebase):

  1. ask_user is a NON-BLOCKING tool. It returns a placeholder result string
     immediately. The engine detects the interruptible result and pauses the
     run loop at the engine level, NOT at the tool level.

  2. The engine is the single source of truth for QuestionRequest state.
     No other layer (tool, REST, WS) may hold or transition this state.

  3. The state machine is strictly:
         pending  →  answered
         pending  →  rejected
         pending  →  expired
     Transitions are non-reversible. Concurrent calls are idempotent:
     the second reply/reject for the same request_id returns a clear error.

  4. The term QuestionRequest is canonical. The legacy alias
     "PendingQuestion" / "Clarification" must not be used in production code;
     they exist only for backwards-compat re-exports.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any, Literal


# ── types ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class QuestionOption:
    """A single selectable option in a question."""
    label: str
    description: str | None = None


@dataclass(frozen=True)
class QuestionPrompt:
    """
    One structured clarification question.

    - multiple=False: user picks at most one option (or one custom string).
    - multiple=True:  user picks 0+ options (or any combination with custom).
    - custom=True:    user may also type free-text as an answer.
    """
    question: str
    options: list[QuestionOption]
    header: str | None = None
    multiple: bool = False
    custom: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "header": self.header,
            "options": [
                {"label": o.label, "description": o.description}
                for o in self.options
            ],
            "multiple": self.multiple,
            "custom": self.custom,
        }


# QuestionAnswer = list[str] (selected labels / custom text for ONE question)
QuestionAnswer = list[str]

# List of answers, one inner list per QuestionPrompt, in the same order
QuestionAnswers = list[QuestionAnswer]


# ── status enum (kept as plain strings for JSON friendliness) ──────────────

QuestionRequestStatus = Literal["pending", "answered", "rejected", "expired"]
QUESTION_STATUS_PENDING: QuestionRequestStatus = "pending"
QUESTION_STATUS_ANSWERED: QuestionRequestStatus = "answered"
QUESTION_STATUS_REJECTED: QuestionRequestStatus = "rejected"
QUESTION_STATUS_EXPIRED: QuestionRequestStatus = "expired"


@dataclass
class QuestionRequest:
    """
    Engine-side storage for one outstanding ask_user invocation.

    State machine (guarded by the engine's lock; non-reversible):
        pending  →  answered    (user submitted valid answers)
        pending  →  rejected    (user clicked Skip)
        pending  →  expired     (engine cancel / timeout / shutdown)

    Invariants:
      - A request is created ONLY by the ask_user tool, but ownership lives
        on the engine. The tool never holds a reference to the request.
      - tool_call_id is the LLM-generated id; the placeholder tool_result
        in the conversation uses this same id (required by
        validate_message_sequence).
      - status transitions are atomic and idempotent.
    """
    request_id: str
    tool_call_id: str
    questions: list[QuestionPrompt]
    submitted_at: float
    status: QuestionRequestStatus = QUESTION_STATUS_PENDING
    answers: QuestionAnswers | None = None  # populated on answered

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_call_id": self.tool_call_id,
            "questions": [q.to_dict() for q in self.questions],
            "submitted_at": self.submitted_at,
            "status": self.status,
        }


# ── validation ──────────────────────────────────────────────────────────────

def validate_answers_against_questions(
    questions: list[QuestionPrompt],
    answers: QuestionAnswers,
) -> tuple[bool, str]:
    """
    Return (ok, error_message). When ok is False, error_message is non-empty.

    Validation rules:
      - answers length must equal questions length
      - each answer is a list[str]
      - for multiple=False: answer length <= 1 (single-select)
      - for multiple=True: answer length <= len(options) + 1 (option count + custom)
      - if custom=False: every label must be in the question's options
      - empty inner lists are allowed (the user simply skipped this question)
    """
    if not isinstance(answers, list):
        return False, "answers must be a list"

    if len(answers) != len(questions):
        return False, (
            f"answers length ({len(answers)}) must equal questions length "
            f"({len(questions)})"
        )

    for i, (q, ans) in enumerate(zip(questions, answers)):
        if not isinstance(ans, list):
            return False, f"answers[{i}] must be a list of strings"
        if any(not isinstance(a, str) for a in ans):
            return False, f"answers[{i}] entries must be strings"

        # Empty answer is fine (user skipped that question).
        if len(ans) == 0:
            continue

        # Single-select: at most one entry
        if not q.multiple and len(ans) > 1:
            return False, f"question {i} is single-select but got {len(ans)} answers"

        # Multi-select: bounded by options + 1 custom entry
        max_allowed = len(q.options) + (1 if q.custom else 0)
        if q.multiple and len(ans) > max_allowed:
            return False, (
                f"question {i}: too many answers ({len(ans)} > {max_allowed})"
            )

        # Validate labels: if custom=False, every entry must be an option label
        if not q.custom:
            valid_labels = {o.label for o in q.options}
            for a in ans:
                if a not in valid_labels:
                    return False, (
                        f"question {i}: {a!r} is not a valid option "
                        f"(custom=false)"
                    )
        else:
            # custom=True: at most 1 entry may be a non-option free text
            option_labels = {o.label for o in q.options}
            custom_entries = [a for a in ans if a not in option_labels]
            if len(custom_entries) > 1:
                return False, (
                    f"question {i}: custom=true allows at most 1 free-text entry"
                )

    return True, ""


# ── text formatting for LLM ────────────────────────────────────────────────

def format_answers_for_llm(
    questions: list[QuestionPrompt],
    answers: QuestionAnswers,
) -> str:
    """
    Format user answers as a clear text block the LLM can read directly.
    This text replaces the placeholder that ask_user returned at interrupt time.
    """
    lines: list[str] = ["User answered the clarification questions:", ""]
    for idx, (q, ans) in enumerate(zip(questions, answers), start=1):
        header = q.header or f"Question {idx}"
        lines.append(f"{idx}. {header}")
        lines.append(f"Question: {q.question}")
        if ans:
            lines.append(f"Answer: {', '.join(ans)}")
        else:
            lines.append("Answer: (skipped)")
        lines.append("")

    # Structured payload so downstream code can parse it
    payload = {"answers": answers}
    lines.append("---structured---")
    lines.append(json.dumps(payload, ensure_ascii=False, indent=2))

    return "\n".join(lines).rstrip()


# ── placeholder text for the non-blocking ask_user return ─────────────────

def format_interrupt_placeholder(request_id: str) -> str:
    """
    The literal string returned by ask_user when it interrupts the engine.

    The loop sees this and treats the corresponding tool_result as
    interruptible; the engine then pauses the run. The frontend sees the
    new pending_question in the snapshot and renders the UI.
    """
    return (
        f"Question posted to the user. request_id={request_id}. "
        f"Awaiting user reply; the engine is paused. Do not proceed with "
        f"the task — wait for the resumed tool_result on the next round."
    )


# ── back-compat re-exports (do NOT use in new code) ────────────────────────
# These are kept only so existing external code (older tests, custom tools)
# that referenced "PendingQuestion" or "QuestionToolOutput" keeps compiling.
# Production code must use QuestionRequest instead.

PendingQuestion = QuestionRequest  # legacy alias


@dataclass(frozen=True)
class QuestionToolOutput:
    """Legacy shape — kept for backwards-compat only."""
    answers: QuestionAnswers

    def to_dict(self) -> dict[str, Any]:
        return {"answers": list(self.answers)}
