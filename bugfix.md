# 停止按钮 Bug 修复记录

## Bug 1：普通停止需要点击两次

### 现象

会话运行过程中点击"停止"，引擎短暂停止后自动重启，需要再点一次。

### 根因

前端 `autoContinueIfNeeded()` 与用户取消冲突：

1. 用户点停止 → `POST /cancel` → 引擎取消，状态变 `WAITING_INPUT`
2. 快照中最后一条消息为 `tool` → `needs_continuation=true`（`engine.py:372-376`）
3. 前端检测到 `needs_continuation=true` → 自动调用 `autoContinueIfNeeded()`（`index.html:4158-4163`）
4. `autoContinueIfNeeded()` 调 `POST /continue` → 引擎重启 → 白取消了

### 修复（双重拦截）

**前端** `static/index.html`：

`cancelSession()`：取消后植入一次性标记
```javascript
autoContinuationKeys.add(`${currentSessionId}:cancel`);
```

`autoContinueIfNeeded()`：检测标记则跳过
```javascript
if (autoContinuationKeys.has(`${sid}:cancel`)) {
    autoContinuationKeys.delete(`${sid}:cancel`);
    return;
}
```

**后端** `harness/engine/engine.py`：

新增 `_user_cancelled` 标记位，服务端持久化，防止刷新后丢失。
- `__init__`：`self._user_cancelled = False`
- `get_snapshot()`：`needs_continuation` 加 `and not self._user_cancelled`
- `cancel()`：设 `self._user_cancelled = True`
- `send_message()`：清除 `self._user_cancelled = False`
- `continue_if_needed()`：加 `if self._user_cancelled: return ignored`

---

## Bug 2：主智能体停止时子智能体不停止

### 现象

`design-primary` 等角色 spawn 子智能体后，点主智能体的停止，子智能体继续运行。主智能体因阻塞在 `spawn_agent` 中无法检查取消信号，直到子智能体自然完成才停，用户需多次点击。

### 根因

`cancel()`（`engine.py:803`）只设置自己的 `_cancel_event`，子智能体各自有独立的 `_cancel_event`（`engine.py:192`），不受影响。

对比 `confirm()` 已有正确传播模式（`engine.py:832-836`），`cancel()` 未使用。

### 修复

`cancel()` 中递归取消所有子智能体：
```python
try:
    from api import rest as rest_module
    for ps in list(self._pending_spawns):
        sub = rest_module._engines.get(ps.sub_id) if hasattr(rest_module, "_engines") else None
        if sub is not None:
            await sub.cancel()
except Exception:
    pass
```

---

## Bug 3：ask_user 后停止 + 刷新复活

### 现象

`ask_user` 工具暂停引擎后点停止，引擎卡在 `WAITING_INTERRUPT` 状态不转换。且停止后刷新页面，引擎又跑起来。

### 根因

- `expire_pending_questions()` 过期了问题但未从 `WAITING_INTERRUPT` 转走，引擎成僵尸状态
- 刷新后前端 `autoContinuationKeys`（内存）丢失，`needs_continuation=true` 触发自动继续

### 修复

`cancel()` 中增加状态转换：
```python
async with self._state_lock:
    if self._sm.state == EngineState.WAITING_INTERRUPT:
        self._sm.transition(EngineState.WAITING_INPUT)
```

结合 Bug 1 的 `_user_cancelled` 标记（服务端持久），防止刷新后 `needs_continuation=true`。

---

## 涉及文件

| 文件 | 改动内容 |
|---|---|
| `harness/engine/engine.py` | 新增 `_user_cancelled`、`cancel()` 递归子智能体 + WAITING_INTERRUPT 转换、`needs_continuation` 检查标记、`continue_if_needed` 防御 |
| `static/index.html` | `cancelSession()` 种 `:cancel` 标记、`autoContinueIfNeeded()` 检测标记 |
