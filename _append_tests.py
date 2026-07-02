extra = '''


# ──────────────────────────────────────────────────────────────────────
# Pending command queue (RUNNING 期间新命令排队)
# ──────────────────────────────────────────────────────────────────────

class _BlockingLLM:
    """Stays inside chat until released — used to force RUNNING state."""
    def __init__(self) -> None:
        self._released = asyncio.Event()

    async def chat(self, messages, tools=None):
        await self._released.wait()
        return Message(role="assistant", content=[TextBlock(text="Done.")])

    async def stream_chat(self, messages, tools=None, on_token=None):
        return await self.chat(messages, tools)

    async def complete(self, prompt):
        return ""

    def release(self) -> None:
        self._released.set()


def _build_blocking_engine(llm):
    session_id = "test-pending-queue"
    emitter = EventEmitter(session_id)
    store = MemorySessionStore()
    registry = ToolRegistry()
    overflow = OverflowStore()
    executor = ToolExecutor(registry=registry, overflow=overflow, emitter=emitter)
    compressor = ContextCompressor(summarizer=llm, config=CompressionConfig())
    loop = ReactLoop(
        llm=llm,
        tool_registry=registry,
        tool_executor=executor,
        compressor=compressor,
        emitter=emitter,
        max_rounds=5,
    )
    return AgentEngine(
        config=EngineConfig(session_id=session_id),
        loop=loop,
        session_store=store,
        emitter=emitter,
        tool_registry=registry,
    )


@pytest.mark.asyncio
async def test_send_message_returns_started_when_idle():
    """First send_message on an idle engine returns status='started'."""
    engine = _build_engine("Reply.")
    result = await engine.send_message("Hello")
    assert result["status"] == "started"
    assert result["queue_size"] == 0
    assert result["queue"] == []


@pytest.mark.asyncio
async def test_send_message_returns_queued_when_running():
    """While the engine is RUNNING, send_message returns status='queued'."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    first = await engine.send_message("first")
    assert first["status"] == "started"
    await asyncio.sleep(0.05)
    assert engine._sm.state == EngineState.RUNNING
    second = await engine.send_message("second")
    assert second["status"] == "queued"
    assert second["index"] == 2
    assert second["text"] == "second"
    assert "submitted_at" in second
    assert second["queue_size"] == 1
    assert second["queue"][0]["index"] == 2
    assert second["queue"][0]["text"] == "second"
    llm.release()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_queue_duplicate_text_keeps_distinct_indexes():
    """Three identical texts in a row must each get a unique index."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    await engine.send_message("1")
    await asyncio.sleep(0.05)
    assert engine._sm.state == EngineState.RUNNING
    r2 = await engine.send_message("1")
    r3 = await engine.send_message("1")
    assert r2["status"] == "queued" and r2["index"] == 2
    assert r3["status"] == "queued" and r3["index"] == 3
    pending = await engine.get_pending_commands()
    assert len(pending) == 2
    assert pending[0]["index"] == 2 and pending[0]["text"] == "1"
    assert pending[1]["index"] == 3 and pending[1]["text"] == "1"
    llm.release()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_cancel_pending_command_by_index():
    """Cancelling one queued entry by index removes only that entry."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    await engine.send_message("live")
    await asyncio.sleep(0.05)
    assert engine._sm.state == EngineState.RUNNING
    await engine.send_message("a")
    await engine.send_message("b")
    await engine.send_message("c")
    pending = await engine.get_pending_commands()
    assert [p["index"] for p in pending] == [2, 3, 4]
    result = await engine.cancel_pending_command(3)
    assert result["cancelled"] is True
    assert result["index"] == 3
    assert result["queue_size"] == 2
    after = await engine.get_pending_commands()
    assert [p["index"] for p in after] == [2, 4]
    assert after[0]["text"] == "a"
    assert after[1]["text"] == "c"
    miss = await engine.cancel_pending_command(999)
    assert miss["cancelled"] is False
    llm.release()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_cancel_pending_does_not_remove_live_message():
    """Cancelling a pending command must NOT remove the live user message."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    await engine.send_message("live")
    await asyncio.sleep(0.05)
    await engine.send_message("queued-only")
    snap_before = await engine.get_snapshot()
    n_before = sum(1 for m in snap_before["last_messages"] if m["role"] == "user")
    assert n_before == 1
    await engine.cancel_pending_command(2)
    snap_after = await engine.get_snapshot()
    n_after = sum(1 for m in snap_after["last_messages"] if m["role"] == "user")
    assert n_after == 1
    llm.release()
    await asyncio.sleep(0.1)
'''
with open('tests/test_engine.py', 'a', encoding='utf-8') as f:
    f.write(extra)
print('appended')
