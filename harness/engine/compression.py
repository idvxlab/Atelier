"""
Two-layer context compression.

Layer 1 — Micro (cheap, no LLM call):
  Triggered when message count grows large.
  Clears ToolResultBlock content in old rounds, preserving structural pairs
  so the message protocol invariant remains valid.

Layer 2 — Auto (expensive, calls a small model):
  Triggered when estimated token usage reaches 65% of the context window.
  Summarizes old messages, then re-injects system identity and task goal.
  Re-injection is MANDATORY — skipping it causes the agent to drift off-topic
  after many rounds because the identity and goal disappear from context.
"""
from __future__ import annotations

from dataclasses import dataclass

from harness.types.messages import Message, TextBlock, ToolResultBlock


@dataclass
class CompressionConfig:
    token_window: int = 128_000
    auto_trigger_ratio: float = 0.65
    micro_keep_recent: int = 6       # keep last N rounds fully intact
    task_goal: str = ""              # injected after every auto-compression
    system_identity: str = ""        # injected after every auto-compression


class ContextCompressor:
    """
    Called once at the start of each round, before the LLM call.
    Mutates the message list in-place (via slice assignment).
    """

    def __init__(self, summarizer, config: CompressionConfig) -> None:
        """
        summarizer: an LLMProvider instance (typically a cheap/small model).
                    Only `complete(prompt: str) -> str` is used.
        """
        self._summarizer = summarizer
        self._cfg = config

    async def maybe_compress(
        self, messages: list[Message], round_idx: int
    ) -> list[Message]:
        tokens = _estimate_tokens(messages)
        ratio = tokens / self._cfg.token_window

        if ratio >= self._cfg.auto_trigger_ratio:
            return await self._auto_compress(messages, round_idx)

        keep_threshold = self._cfg.micro_keep_recent * 4
        if len(messages) > keep_threshold:
            return self._micro_compress(messages)

        return messages

    # ------------------------------------------------------------------
    # Layer 1: Micro — clear old tool result content
    # ------------------------------------------------------------------

    def _micro_compress(self, messages: list[Message]) -> list[Message]:
        keep_from = max(0, len(messages) - self._cfg.micro_keep_recent * 2)
        result: list[Message] = []
        for i, msg in enumerate(messages):
            if i < keep_from and msg.role == "tool":
                new_blocks = []
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        new_blocks.append(
                            ToolResultBlock(
                                tool_call_id=block.tool_call_id,
                                content="[cleared by micro-compression]",
                                is_error=block.is_error,
                            )
                        )
                    else:
                        new_blocks.append(block)
                result.append(
                    Message(
                        role=msg.role,
                        content=new_blocks,
                        round_index=msg.round_index,
                        is_compressed=True,
                    )
                )
            else:
                result.append(msg)
        return result

    # ------------------------------------------------------------------
    # Layer 2: Auto — summarize + re-inject identity and goal
    # ------------------------------------------------------------------

    async def _auto_compress(
        self, messages: list[Message], round_idx: int
    ) -> list[Message]:
        cfg = self._cfg
        keep_from = max(0, len(messages) - cfg.micro_keep_recent * 2)
        old_msgs = messages[:keep_from]
        recent_msgs = messages[keep_from:]

        summary_prompt = _build_summary_prompt(old_msgs)
        summary_text = await self._summarizer.complete(summary_prompt)

        rebuilt: list[Message] = []

        # Re-inject system identity (MANDATORY after any auto-compression)
        if cfg.system_identity:
            rebuilt.append(
                Message(
                    role="system",
                    content=[TextBlock(text=cfg.system_identity)],
                    round_index=0,
                    is_compressed=True,
                )
            )

        # Re-inject task goal (prevents multi-round topic drift)
        if cfg.task_goal:
            rebuilt.append(
                Message(
                    role="user",
                    content=[TextBlock(text=f"[Task goal reminder]: {cfg.task_goal}")],
                    round_index=0,
                    is_compressed=True,
                )
            )

        # Conversation summary replaces all old messages
        rebuilt.append(
            Message(
                role="user",
                content=[
                    TextBlock(
                        text=(
                            f"[Conversation summary up to round {round_idx}]:\n"
                            f"{summary_text}"
                        )
                    )
                ],
                round_index=round_idx,
                is_compressed=True,
            )
        )

        rebuilt.extend(recent_msgs)
        return rebuilt


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _estimate_tokens(messages: list[Message]) -> int:
    """Fast approximation: 4 chars ≈ 1 token."""
    total = 0
    for msg in messages:
        for block in msg.content:
            if hasattr(block, "text"):
                total += len(block.text)
            elif hasattr(block, "content"):
                total += len(block.content)
            elif hasattr(block, "thinking"):
                total += len(block.thinking)
            elif hasattr(block, "tool_input"):
                total += len(str(block.tool_input))
    return total // 4


def _build_summary_prompt(messages: list[Message]) -> str:
    lines = [
        "Summarize the following conversation history concisely. "
        "Preserve: decisions made, files modified, errors encountered, "
        "tools called and their outcomes, and current state of work. "
        "Do NOT include raw tool outputs verbatim.\n"
    ]
    for msg in messages:
        for block in msg.content:
            if isinstance(block, TextBlock) and block.text.strip():
                lines.append(f"[{msg.role}]: {block.text[:500]}")
    return "\n".join(lines)
