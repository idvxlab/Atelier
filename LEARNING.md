# Agent Harness 学习指南

> 从零理解：什么是 harness，为什么需要它，怎么一步步构建

---

## 第一章：什么是 Agent Harness

### 1.1 从一个比喻开始

你想让一匹马拉车。马很强壮（就像 LLM 很聪明），但如果没有**挽具（harness）**，你没办法控制它的力量，它也不知道该往哪走、何时停。

Harness 就是挽具：

```
没有 harness：
  用户 → 直接问 LLM → LLM 回答一句话 → 结束

有了 harness：
  用户 → harness 接收请求
              ↓
         harness 决定是否调用工具
              ↓
         harness 执行工具，把结果告诉 LLM
              ↓
         harness 判断：完成了吗？还要继续吗？
              ↓
         harness 管理上下文不超限
              ↓
         用户得到最终结果
```

### 1.2 专业定义

**Agent Harness** 是一个运行时框架，它：

1. **驱动 LLM 循环运行**（不是一问一答，而是持续推理）
2. **管理 LLM 与工具之间的通信协议**（工具调用 → 结果回写）
3. **控制会话的生命周期**（开始、暂停、取消、出错、恢复）
4. **处理上下文长度限制**（token 窗口满了要压缩）
5. **提供安全防护**（防注入、防死循环、限制输出大小）
6. **对外暴露接口**（REST API、WebSocket）

### 1.3 和"直接调用 LLM"有什么区别

| 场景 | 直接调 API | 用 Harness |
|------|-----------|-----------|
| 简单问答 | ✅ 够用 | 过重 |
| 需要查文件、执行命令 | ❌ 做不到 | ✅ |
| 多轮任务（写代码→测试→修复） | ❌ 需要自己管状态 | ✅ 自动 |
| 上下文超出 token 限制 | ❌ 报错 | ✅ 自动压缩 |
| 需要随时取消 | ❌ 没有机制 | ✅ 即时生效 |
| 多个 LLM 供应商 | ❌ 各改一遍 | ✅ 换一个配置 |

---

## 第二章：核心概念——ReAct 循环

### 2.1 什么是 ReAct

ReAct = **Re**asoning + **Act**ing（推理 + 行动）

这是 Agent 的核心思维模式，来自 2022 年的论文《ReAct: Synergizing Reasoning and Acting in Language Models》。

基本想法：**让 LLM 交替做两件事——思考下一步该做什么，然后真的去做。**

### 2.2 ReAct 循环流程图

```
              ┌─────────────────────────────────────┐
              │            开始一轮                   │
              └────────────────┬────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   把消息历史发给 LLM  │
                    └──────────┬──────────┘
                               │
              ┌────────────────▼────────────────────┐
              │    LLM 回复了什么？                  │
              └────────────────┬────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
    ┌──────────▼──────────┐       ┌────────────▼────────────┐
    │  只有文字（没有工具） │       │ 要调用工具（ToolCallBlock）│
    └──────────┬──────────┘       └────────────┬────────────┘
               │                               │
    ┌──────────▼──────────┐       ┌────────────▼────────────┐
    │   任务完成，结束循环  │       │   执行工具，拿到结果      │
    └─────────────────────┘       └────────────┬────────────┘
                                               │
                                  ┌────────────▼────────────┐
                                  │  把结果写回消息历史       │
                                  └────────────┬────────────┘
                                               │
                                  ┌────────────▼────────────┐
                                  │    进入下一轮循环         │
                                  └─────────────────────────┘
```

### 2.3 最简单的 ReAct 实现（20 行）

```python
async def react_loop(messages, llm, tools, max_rounds=10):
    for _ in range(max_rounds):
        # 1. 问 LLM
        reply = await llm.chat(messages, tools)
        messages.append(reply)

        # 2. 如果没有工具调用，说明 LLM 认为任务完成
        if not reply.has_tool_calls():
            return messages   # 结束

        # 3. 执行工具
        results = []
        for call in reply.tool_calls():
            output = await execute_tool(call)
            results.append(output)

        # 4. 把结果写回历史
        messages.append(tool_result_message(results))
        # 进入下一轮
```

这就是最核心的逻辑。真实 harness 在这基础上加了很多保护和功能。

---

## 第三章：消息协议——最容易踩坑的地方

### 3.1 为什么消息顺序很重要

OpenAI 和 Anthropic 都要求：**如果 AI 说"我要调用工具"，那下一条消息必须是工具的结果，中间不能有任何其他消息。**

违反这个规则 → API 直接返回 400 错误，告诉你请求格式非法。

### 3.2 合法的消息序列

```
消息 0: user    "帮我列出当前目录的文件"
消息 1: assistant [ToolCallBlock: shell("ls -la")]   ← AI 要调用工具
消息 2: tool    [ToolResultBlock: "file1.py\nfile2.py"]  ← 必须紧跟！
消息 3: assistant "目录下有两个文件：file1.py 和 file2.py"
```

### 3.3 非法的消息序列（会报 400）

```
消息 1: assistant [ToolCallBlock: shell("ls")]
消息 2: user "等一下，先别做"    ← ❌ 插入用户消息！
消息 3: tool [ToolResultBlock: ...]
```

### 3.4 这带来了一个并发难题

用户在 AI 调用工具的过程中，可能会发来新消息。**不能直接插入！** 正确做法：

```python
# 用户发消息时，AI 正在等待工具结果
用户消息 → 放进队列 → 等工具结果写完 → 再把用户消息插入
```

这就是 `intervention_queue` 的来源。

### 3.5 OpenAI 和 Anthropic 的格式差异

虽然概念相同，但 API 格式完全不一样：

**OpenAI：** 工具结果是独立的消息
```json
{"role": "tool", "tool_call_id": "call_abc", "content": "file1.py"}
```

**Anthropic：** 工具结果嵌套在用户消息里
```json
{
  "role": "user",
  "content": [{"type": "tool_result", "tool_use_id": "toolu_abc", "content": "file1.py"}]
}
```

这就是为什么需要适配层——你的内部消息格式统一，适配层负责转换。

---

## 第四章：状态机——控制 Agent 的生命周期

### 4.1 为什么需要状态机

没有状态机时可能出现的问题：
- 用户快速点击"发送"两次 → 启动了两个并发循环 → 消息顺序混乱
- 循环还没结束就被取消 → 状态没有正确清理 → 下次无法启动
- 出错了不知道能不能继续 → 用户不知道该怎么操作

状态机强制规定：**每个状态下，只允许特定的操作。**

### 4.2 Agent 的完整状态图

```
                  用户发消息
  WAITING_INPUT ──────────────► RUNNING ──────► COMPLETED
       ▲                          │                │
       │                          │ 出错            │ 用户再发消息
       │   取消                   ▼                │
       └─────────────────────── ERROR ◄────────────┘
                                  │
                                  │ 用户选择恢复
                                  └──► WAITING_INPUT

  另外还有：
  WAITING_CONFIRMATION（AI 要做危险操作，等用户确认）
```

### 4.3 状态转换的代码实现思路

```python
ALLOWED_TRANSITIONS = {
    "WAITING_INPUT":        {"RUNNING", "ERROR"},
    "RUNNING":              {"WAITING_INPUT", "COMPLETED", "ERROR", "WAITING_CONFIRMATION"},
    "COMPLETED":            {"WAITING_INPUT"},   # 允许复用会话
    "ERROR":                {"WAITING_INPUT"},   # 允许恢复
    "WAITING_CONFIRMATION": {"RUNNING", "WAITING_INPUT", "ERROR"},
}

def transition(current_state, new_state):
    if new_state not in ALLOWED_TRANSITIONS[current_state]:
        raise Error(f"非法转换: {current_state} → {new_state}")
    return new_state
```

**重要设计决策：取消 → WAITING_INPUT，不是 ERROR**

取消是用户主动操作，不是系统故障。所以取消后应该回到"等待输入"，用户还可以继续发消息，不应该进入"错误"状态。

---

## 第五章：并发——最难的部分

### 5.1 核心问题

Agent 是异步的（用户不等待，AI 在后台跑）。但以下情况会同时发生：

- 用户在发消息（写操作）
- AI 在生成回复（读操作）
- 工具在执行（并发写操作）
- 前端在查询状态（读操作）

如果不处理好，会出现**竞态条件（race condition）**。

### 5.2 最重要的并发规则：锁里不做慢操作

**错误做法（会死锁/变慢）：**
```python
async with lock:
    state = "RUNNING"
    await llm.chat(...)     # ❌ 在锁里等 LLM 返回！可能等30秒！
    state = "COMPLETED"
```

**正确做法：**
```python
async with lock:
    state = "RUNNING"       # ✅ 只改状态（瞬间完成）
# 锁已释放 ↑

asyncio.create_task(run_loop())  # ✅ 在锁外异步运行
```

### 5.3 取消机制的实现

取消不是"强制杀死"，而是"设置一个信号，让循环自己停"：

```python
cancel_event = asyncio.Event()

# 取消时
cancel_event.set()   # 设置信号

# 循环里
for round in range(max_rounds):
    if cancel_event.is_set():
        raise CancelledError()   # 自己停下来

    # 但如果 LLM 调用需要 30 秒怎么办？
    # 需要让 LLM 调用和取消信号竞速！
    done, _ = await asyncio.wait(
        [llm_task, cancel_task],
        return_when=asyncio.FIRST_COMPLETED
    )
```

**这是一个容易遗漏的 bug：** 只在循环开头检查取消是不够的，LLM 调用本身也要能被中断。

### 5.4 三条路径保证状态归还

无论发生什么，引擎都必须从 RUNNING 退出到某个确定状态：

```python
async def run_guarded():
    try:
        await loop.run(...)
        state = "COMPLETED"          # 正常完成

    except asyncio.CancelledError:
        state = "WAITING_INPUT"      # 取消（可恢复）

    except Exception:
        state = "ERROR"              # 出错（可恢复）

    finally:
        save_session()               # 无论如何都要持久化
```

如果漏掉任何一条路径，引擎会永远卡在 RUNNING，用户再也无法发消息。

---

## 第六章：上下文压缩——解决 token 限制

### 6.1 问题背景

LLM 有 token 限制（如 128k）。一轮对话大约消耗 500-2000 token。做 100 轮工具调用后，历史可能超出限制。

**不处理 → API 报错，任务中断。**

### 6.2 两层压缩策略

**为什么要两层？** 因为代价不同：

| 层次 | 触发条件 | 操作 | 代价 |
|------|---------|------|------|
| Micro（轻量） | 消息数量超过阈值 | 清除旧工具输出内容 | 零 API 调用 |
| Auto（精确） | Token 估算超过 65% | 用小模型生成摘要 | 一次 API 调用 |

**Micro 压缩：**
```
之前：
  [assistant] 调用 shell("ls")
  [tool]      "file1.py\nfile2.py\n..."（很长）

之后：
  [assistant] 调用 shell("ls")
  [tool]      "[已清除]"           ← 结构还在，但内容删掉了
```

为什么不把整条消息删掉？因为删掉 `assistant tool_call` 消息的话，后面的 `tool_result` 消息就成了孤儿，违反协议。

**Auto 压缩：**
```
把前 N 条消息 → 发给便宜的小模型 → 生成摘要
替换为：
  [system]  "你是一个编程助手"          ← 重新注入身份！
  [user]    "任务：修复登录 bug"         ← 重新注入目标！
  [user]    "之前的进展摘要：已完成X、Y"
  [之后的消息...]
```

### 6.3 最关键的细节：压缩后必须重新注入身份和目标

**如果不重新注入：**
- AI 在第 50 轮可能"忘记"自己是编程助手
- AI 在第 80 轮可能"忘记"任务目标是修复登录 bug
- 开始做不相关的事情

这是实际生产中最容易忽略的 bug。

---

## 第七章：工具层——安全地扩展 AI 的能力

### 7.1 工具的本质

工具就是：**一个有名字、有参数描述的异步函数。**

```python
# 工具的描述（给 LLM 看）
schema = ToolSchema(
    name="read_file",
    description="读取文件内容",
    params=[ToolParam(name="path", type="string", description="文件路径")]
)

# 工具的实现（实际执行）
async def read_file_tool(path: str) -> str:
    with open(path) as f:
        return f.read()
```

LLM 看到 schema，决定是否调用。Harness 执行实际函数，把结果返回给 LLM。

### 7.2 为什么每轮都要重新加载工具列表

```python
# 错误做法
tools = registry.get_tools()   # 只加载一次
for round in range(max_rounds):
    reply = await llm.chat(messages, tools)  # 用旧的工具列表

# 正确做法
for round in range(max_rounds):
    tools = registry.get_tools()  # 每轮重新加载
    reply = await llm.chat(messages, tools)
```

原因：工具可能在运行时动态注册（比如 AI 调用某个工具后，这个工具又注册了新工具）。如果缓存了，AI 永远看不到新工具。

### 7.3 输出限制——防止 LLM 被淹没

工具可能返回巨大的输出（比如读取一个 10MB 的日志文件）。如果全部塞进上下文，会占满 token 窗口。

解决方案：设置硬上限，超出的部分存到外部，返回引用 ID：

```python
output = await tool.run()   # "...10MB 的内容..."
if len(output) > 20000:
    ref_id = storage.save(output)
    return f"[输出太大，已存储，引用 ID: {ref_id}]"
```

AI 可以在后续轮次用这个 ID 请求具体片段。

### 7.4 Shell 安全：永远用数组参数

```python
# ❌ 危险：用户输入可以注入命令
user_input = "test.py; rm -rf /"
subprocess.run(f"python {user_input}", shell=True)
# 执行了 python test.py; rm -rf /  ← 灾难！

# ✅ 安全：数组参数，shell 不会解析特殊字符
asyncio.create_subprocess_exec("python", user_input)
# 只会尝试执行名为 "test.py; rm -rf /" 的文件（找不到，安全报错）
```

---

## 第八章：可观测性——知道 Agent 在干什么

### 8.1 为什么难以调试

Agent 的问题在于：它在后台运行，你看不到它在哪一步出了问题。

常见的调试困境：
- "AI 为什么不调用工具？"
- "工具调用了，但结果怎么没有写回去？"
- "上下文压缩触发了吗？"
- "取消信号发出去了，但 AI 还在跑？"

### 8.2 决策点 vs 执行点

**错误的埋点方式（执行点）：**
```python
async def execute_tool(call):
    result = await tool.run()
    logger.info(f"工具执行完成: {call.name}")  # 只知道"做了"
    return result
```

**正确的埋点方式（决策点）：**
```python
# 在"该不该做"的地方埋点
tool = registry.get(call.name)
if tool is None:
    logger.info({"event": "tool_call", "state": "execution-error", "reason": "not_found"})
    # 知道了：工具根本不存在
else:
    logger.info({"event": "tool_call", "state": "triggered-executed"})
    result = await tool.run()
```

### 8.3 四种事件状态

| 状态 | 含义 | 例子 |
|------|------|------|
| `triggered-executed` | 触发了，正常运行 | 工具调用成功 |
| `condition-not-met` | 检查了，条件不满足，没运行 | 取消信号检查：没有取消信号 |
| `triggered-intercepted` | 触发了，但被拦截 | 工具输出超限，存到外部 |
| `execution-error` | 运行了，但出错 | 工具抛出异常 |

**没有事件 = 最危险的信号**

如果你完全看不到某个事件（比如 `tool_call`），说明那段代码根本没有执行到，可能有逻辑路径没有走到，比 "执行了但出错" 更难排查。

---

## 第九章：从零构建一个最简版 Harness

如果你要从头搭一个最简 harness，最少需要以下组件，按顺序搭建：

### Step 1：定义消息类型（1 小时）

```python
from dataclasses import dataclass, field
from typing import Literal, Union

@dataclass
class TextBlock:
    text: str

@dataclass
class ToolCallBlock:
    tool_call_id: str
    tool_name: str
    tool_input: dict

@dataclass
class ToolResultBlock:
    tool_call_id: str
    content: str
    is_error: bool = False

@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: list   # list of blocks above
```

### Step 2：接一个 LLM（1 小时）

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="...")

async def call_llm(messages: list[Message], tools) -> Message:
    # 转换格式
    oai_messages = [to_openai_format(m) for m in messages]
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=oai_messages,
        tools=tools,
    )
    # 解析回复
    return parse_response(response)
```

### Step 3：接一个工具（30 分钟）

```python
import asyncio, shlex

async def shell_tool(command: list[str]) -> str:
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode()
```

### Step 4：写 ReAct 循环（1 小时）

```python
async def run(user_input: str):
    messages = [
        Message(role="system", content=[TextBlock("你是一个助手")]),
        Message(role="user",   content=[TextBlock(user_input)]),
    ]
    tools = [shell_schema]  # 告诉 LLM 有哪些工具

    for _ in range(20):     # 最多跑 20 轮
        reply = await call_llm(messages, tools)
        messages.append(reply)

        if not any(isinstance(b, ToolCallBlock) for b in reply.content):
            break   # 没有工具调用，结束

        # 执行工具
        results = []
        for call in [b for b in reply.content if isinstance(b, ToolCallBlock)]:
            output = await shell_tool(call.tool_input["command"])
            results.append(ToolResultBlock(call.tool_call_id, output))

        messages.append(Message(role="tool", content=results))

    return messages
```

这 4 步，你就有了一个能用的最简 Agent。之后再逐步加：状态机、取消、压缩、持久化、API 层。

---

## 第十章：常见设计陷阱

### 陷阱 1：在工具结果和下一个用户消息之间插入消息

```
❌ 错误：
assistant → tool_call
user      → "等等"      ← 插入了用户消息！
tool      → tool_result
→ API 400 错误

✅ 正确：
assistant → tool_call
tool      → tool_result    ← 必须紧跟
user      → "等等"         ← 等工具结果写完再插
```

### 陷阱 2：取消后不清理状态

```python
# ❌ 错误
await engine.cancel()
# 状态还是 RUNNING，用户再也没法发消息

# ✅ 正确：CancelledError 里要处理
except asyncio.CancelledError:
    state = "WAITING_INPUT"   # 归还状态
```

### 陷阱 3：压缩后不重新注入 system prompt

```python
# ❌ 错误：压缩直接替换消息
messages = [summary_msg] + recent_msgs
# AI 忘了自己是谁，忘了任务目标

# ✅ 正确
messages = [system_identity_msg, task_goal_msg, summary_msg] + recent_msgs
```

### 拦截 4：在锁里等待 I/O

```python
# ❌ 错误：锁里等 LLM（可能等 30 秒）
async with lock:
    state = "RUNNING"
    reply = await llm.chat(...)   # 锁一直持有！

# ✅ 正确：锁里只改状态
async with lock:
    state = "RUNNING"
# 锁释放后再做 I/O
reply = await llm.chat(...)
```

### 陷阱 5：只在轮次开头检查取消

```python
# ❌ 不够：LLM 调用 30 秒，期间取消无效
for round in range(max_rounds):
    if cancel_event.is_set():
        break
    reply = await llm.chat(...)   # 被卡在这里

# ✅ 正确：让 LLM 调用和取消信号竞速
llm_task = asyncio.ensure_future(llm.chat(...))
cancel_task = asyncio.ensure_future(cancel_event.wait())
done, _ = await asyncio.wait([llm_task, cancel_task], return_when=FIRST_COMPLETED)
if cancel_event.is_set():
    llm_task.cancel()
    raise CancelledError()
```

### 陷阱 6：缓存工具列表

```python
# ❌ 错误：只加载一次
tools = registry.all_tools()
for round in range(max_rounds):
    reply = await llm.chat(messages, tools)   # 看不到新工具

# ✅ 正确：每轮重新加载
for round in range(max_rounds):
    tools = registry.all_tools()   # 每次都取最新的
    reply = await llm.chat(messages, tools)
```

---

## 第十一章：关键术语速查

| 术语 | 解释 |
|------|------|
| **ReAct** | 推理+行动的循环模式，Agent 的核心思维方式 |
| **Tool Call** | AI 请求调用某个工具的消息块 |
| **Tool Result** | 工具执行后的返回结果，必须紧跟 Tool Call |
| **Context Window** | LLM 能看到的最大 token 数量 |
| **Micro Compression** | 清除旧工具输出内容（廉价） |
| **Auto Compression** | 用小模型生成摘要（精确） |
| **State Machine** | 控制 Agent 生命周期，防止非法操作 |
| **Race Condition** | 并发操作顺序不确定导致的 bug |
| **Intervention Queue** | 临时存放用户消息，等待安全时机插入 |
| **Overflow Store** | 存放超大工具输出，避免占满上下文 |
| **Observability** | 可观测性：知道系统内部在发生什么 |
| **Single Source of Truth** | 单一真相源：状态只在一个地方维护 |

---

## 附录：学习路径建议

```
阶段 1（理解）：
  读懂 types/messages.py → 理解消息协议
  读懂 engine/state_machine.py → 理解状态机
  读懂 engine/loop.py → 理解 ReAct 循环

阶段 2（动手）：
  跑通 tests/test_llm.py → 理解协议验证
  跑通 tests/test_engine.py → 理解状态机和引擎

阶段 3（扩展）：
  给 ToolRegistry 注册一个自定义工具
  修改 CompressionConfig 调整压缩阈值
  写一个新的 LLMProvider（比如接 Google Gemini）

阶段 4（集成）：
  配置 config.yaml 填入真实 API Key
  启动 uvicorn api.rest:app
  用 curl 或者 Postman 测试完整的对话流程
```
