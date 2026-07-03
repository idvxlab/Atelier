# MyHarnessPy 使用手册

> 面向导师 / 使用者的操作参考。无需了解底层代码，按需配置即可。

---

## 目录

1. [快速启动](#一快速启动)
2. [内置工具](#二内置工具)
3. [Persona — Agent 身份配置](#三persona--agent-身份配置)
4. [Skill — 可调用流程库](#四skill--可调用流程库)
5. [CLI 操作手册](#五cli-操作手册)
6. [Web UI 操作手册](#六web-ui-操作手册)
7. [提问模式（Stage 4）— AI 主动澄清模糊需求](#七提问模式stage-4--ai-主动澄清模糊需求)
8. [config.yaml 参数说明](#八configyaml-参数说明)

---

## 一、快速启动

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动 Web 服务（推荐）

uvicorn api.rest:app --reload --port 8000# 浏览器打开 http://localhost:8000

# 或直接用 CLI（无需启动服务器）
python cli.py --persona coder
```

API Key 通过 `.env` 文件或环境变量配置：

```bash
# .env 文件
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

---

## 二、内置工具

Agent 可使用以下工具执行任务。工具由 `config.yaml` 的 `tools.enabled` 全局控制，Persona 可进一步限制每个身份能用的工具子集。

### `read_file` — 读取文件

读取本地文件内容，支持分段读取。

| 参数     | 类型    | 必填 | 说明                      |
| -------- | ------- | ---- | ------------------------- |
| `path`   | string  | ✓    | 文件路径                  |
| `offset` | integer | —    | 起始行（从 0 计，默认 0） |
| `limit`  | integer | —    | 读取行数上限              |

- 输出上限：**20,000 字符**（超出自动存入引用，Agent 可按需读取）
- 典型用途：读源代码、日志文件、配置文件

---

### `search` — 正则搜索

在文件或目录中搜索匹配行，返回 `文件名:行号: 内容` 格式。

| 参数             | 类型    | 必填 | 说明                        |
| ---------------- | ------- | ---- | --------------------------- |
| `pattern`        | string  | ✓    | 正则表达式或字面字符串      |
| `path`           | string  | ✓    | 文件或目录路径              |
| `case_sensitive` | boolean | —    | 是否大小写敏感（默认 true） |
| `max_results`    | integer | —    | 最多返回行数（默认 100）    |

- 输出上限：**10,000 字符**
- 典型用途：在代码库中搜索函数、变量、错误信息

---

### `shell` — 执行命令

执行系统命令，返回 stdout + stderr 合并输出。

| 参数      | 类型   | 必填 | 说明                               |
| --------- | ------ | ---- | ---------------------------------- |
| `command` | array  | ✓    | 命令和参数数组，如 `["ls", "-la"]` |
| `cwd`     | string | —    | 工作目录（默认 `.`）               |
| `timeout` | number | —    | 超时秒数（默认 30）                |

- 输出上限：**15,000 字符**
- 安全：内部使用 `subprocess_exec`（非 shell=True），防止命令注入
- 如需禁用：在 `config.yaml` 的 `tools.enabled` 中注释掉 `shell` 行

---

### `web_search` — 联网搜索

在公网上搜索，返回结构化结果（标题、URL、摘要、排名、提供方）。

| 参数          | 类型    | 必填 | 说明                          |
| ------------- | ------- | ---- | ----------------------------- |
| `query`       | string  | ✓    | 搜索词                        |
| `max_results` | integer | —    | 最大结果数（默认 5，最大 10） |

**搜索后端优先级**（在 `web_search_tool` 内部按此顺序探测）：

| 优先级 | 提供方                                | 需要的 Key             | 推荐场景                                           |
| ------ | ------------------------------------- | ---------------------- | -------------------------------------------------- |
| 1      | **Serper.dev**（Google 结果）         | `SERPER_API_KEY`       | ★ 首选：中文/英文都强，每月 2,500 次免费           |
| 2      | **Brave Search**                      | `BRAVE_SEARCH_API_KEY` | 海外替代，质量接近 Google                          |
| 3      | **DuckDuckGo Instant Answer**（兜底） | 无                     | **仅做事实查询**（天气、定义），不是真正的网页搜索 |

#### 推荐配置：Serper（Google 搜索）

1. 去 https://serper.dev 注册（GitHub/Google 账号即可）
2. Dashboard 复制 API Key
3. 在 `.env` 加一行：`SERPER_API_KEY=你的key`
4. 重启 harness 即可

返回结果示例：

```json
{
  "ok": true,
  "provider": "serper",
  "query": "Python 异步编程",
  "result_count": 8,
  "results": [
    {
      "rank": 1,
      "title": "Python asyncio 官方文档",
      "url": "https://docs.python.org/3/library/asyncio.html",
      "snippet": "asyncio is a library to write concurrent code...",
      "date": "2 days ago",
      "source": "google_serper"
    },
    ...
  ],
  "knowledge_graph": {"title": "Python", "description": "..."},
  "people_also_ask": [{"question": "...", "snippet": "..."}],
  "related_searches": ["python coroutine", ...],
  "meta": {"credits_used": 1}
}
```

#### 不配置 Key 会发生什么

会走 DDG Instant Answer 兜底，返回结构化但**几乎是空**的结果（DDG 只回答事实型问题，不做网页搜索）。要看到真实搜索结果，**必须配置至少一个 Key**。

---

### `web_fetch` — 抓取网页正文

抓取公开 HTTP/HTTPS URL 的 HTML，自动**提取正文**返回给 LLM（而不是整页 HTML）。

| 参数         | 类型    | 必填 | 说明                                      |
| ------------ | ------- | ---- | ----------------------------------------- |
| `url`        | string  | ✓    | 公开 URL                                  |
| `max_length` | integer | —    | 最大返回字符数（默认 8,000，最大 50,000） |

**HTML → 正文提取策略**（依次尝试）：

1. **trafilatura**：业内最权威的开源正文提取器，自动剥离导航、侧栏、广告、相关链接
2. **BeautifulSoup**：兜底，找出 `<main>`/`<article>` 区域
3. **正则剥标签**：最后兜底（去 `<script>/<style>` 后去所有标签）

**User-Agent**：默认是 Chrome 124 UA，可被 `WEB_FETCH_USER_AGENT` 环境变量覆盖。

**安全限制**：

- 屏蔽 localhost、私网 IP（SSRF 防护）
- URL 长度 ≤ 2 MB（防止下载巨型响应）
- 跟随最多 5 次重定向

---

### `use_skill` — 加载 Skill

加载指定 Skill 的详细说明，Agent 在判断任务匹配时自动调用（也可手动调用）。

| 参数   | 类型   | 必填 | 说明                                       |
| ------ | ------ | ---- | ------------------------------------------ |
| `name` | string | ✓    | Skill 名称，如 `code-review`、`python-dev` |

- 此工具**始终可用**，不受 `config.yaml tools.enabled` 控制
- Agent 从 system prompt 中看到 skill 描述列表，自主判断何时调用

---

## 三、Persona — Agent 身份配置

Persona 定义 Agent 的 **身份、行为规范和工具权限**。每个 Session 在创建时选择一个 Persona。

### 文件位置

```
personas/
  default.md          ← 通用助手
  coder.md            ← 资深工程师
  researcher.md       ← 学术研究助手
  strict-reviewer.md  ← 严格代码审查员
  <你的名字>.md        ← 自定义
```

### 文件格式

```markdown
---
name: coder
description: "资深工程师，写完整可运行的代码"
allowed_tools:
  - read_file
  - search
  - shell
# provider: bltcy-anthropic   # 可选：指定该身份使用的 provider
---

你是一个资深软件工程师，有 10 年以上工程经验。

写代码时：

- 给出完整可运行的代码，不要给残缺片段
  ...
```

| 字段            | 说明                                                   |
| --------------- | ------------------------------------------------------ |
| `name`          | Persona 标识（即文件名，不带 .md）                     |
| `description`   | 一句话描述，显示在前端和 CLI 列表里                    |
| `allowed_tools` | 允许使用的工具列表；省略 = 使用 config.yaml 的全局设置 |
| `provider`      | 可选，覆盖默认 provider                                |
| 正文（---之后） | System Prompt 内容，直接定义 Agent 的角色和行为        |

### 新建 Persona

1. 在 `personas/` 目录创建 `<name>.md`，按上面格式填写
2. 重启服务（或前端刷新后在侧边栏点击 Persona 名即可使用）

---

## 四、Skill — 可调用流程库

Skill 是 **某类任务的最佳实践流程**，由 Agent 在对话中自主判断调用（也可用户手动触发）。与 Persona 不同，Skill 不在创建 Session 时绑定——而是在整个 Session 中随时可用。

### 工作原理

```
Session 启动
  → 所有 Skill 的 name + description 注入 system prompt
  → Agent 根据用户请求，判断是否匹配某个 Skill
  → 匹配时调用 use_skill(name="...") 工具
  → 完整 SKILL.md 正文加载，Agent 遵循其中步骤执行
```

### 文件位置

```
skills/
  code-review/
    SKILL.md          ← 必需，主文件
    checklist.md      ← 可选，支持文件
  python-dev/
    SKILL.md
  data-analyst/
    SKILL.md
  file-organizer/
    SKILL.md
  <你的名字>/
    SKILL.md
```

### SKILL.md 格式

```markdown
---
name: code-review
description: "代码审查。当用户要求审查代码、检查质量或发现 bug 时使用。"
# disable-model-invocation: true   # 取消注释 = 只能用户手动调用
---

你是一个资深软件工程师，专注于代码审查。

审查时按以下维度分析：

1. **正确性** — 逻辑是否正确，边界情况是否处理
2. **安全性** — 是否有注入风险、权限漏洞
   ...
```

| 字段                       | 说明                                                       |
| -------------------------- | ---------------------------------------------------------- |
| `name`                     | Skill 标识（一般与文件夹名一致）                           |
| `description`              | **关键**：Agent 靠这句话判断何时使用该 Skill               |
| `disable-model-invocation` | `true` = Agent 不自动调用，只能用户手动 `/skill-name` 触发 |
| 正文（---之后）            | Skill 的详细执行说明，调用时才加载                         |

### 新建 Skill

```bash
# 1. 创建文件夹和主文件
mkdir skills/my-skill
cp skills/template/SKILL.md skills/my-skill/SKILL.md

# 2. 编辑 skills/my-skill/SKILL.md
# 3. 重启服务，Skill 自动生效
```

### 支持文件

SKILL.md 可以引用同目录下的其他文件：

```
my-skill/
  SKILL.md            ← 主说明（引用下面两个文件）
  reference.md        ← 详细参考资料（Agent 按需读取）
  scripts/
    validate.sh       ← 脚本（Agent 可通过 shell 工具执行）
```

在 SKILL.md 中引用：

```markdown
详细 API 参考见 [reference.md](reference.md)
验证脚本：scripts/validate.sh
```

---

## 五、CLI 操作手册

### 启动方式

```bash
# 基本启动（使用 config.yaml 默认设置）
python cli.py

# 指定 provider
python cli.py --provider bltcy-openai

# 指定 Persona（推荐，包含身份 + 工具权限）
python cli.py --persona coder
python cli.py --persona researcher

# 列出所有可用 Persona
python cli.py --list-personas

# 手动指定 System Prompt（不推荐，Persona 更规范）
python cli.py --system "你是一个 Python 专家"

# 显示内部事件流（调试用）
python cli.py --verbose
python cli.py -v
```

### 对话中的命令

| 命令               | 说明                                      |
| ------------------ | ----------------------------------------- |
| `/exit` 或 `/quit` | 退出                                      |
| `/reset`           | 开启新会话（保留当前 Persona 和工具配置） |
| `/tools`           | 列出当前会话可用的工具                    |
| `/skills`          | 列出所有可用 Skill（及描述）              |
| `/personas`        | 列出所有可用 Persona（及描述）            |
| `/state`           | 显示引擎当前状态和消息数量                |
| `/<skill-name>`    | 手动调用某个 Skill，如 `/code-review`     |

### 示例对话

```
$ python cli.py --persona coder
╔══════════════════════════════════════╗
║      MyHarnessPy  Interactive CLI    ║
╚══════════════════════════════════════╝
  Provider : bltcy-anthropic
  Model    : claude-sonnet-4-6
  Persona  : coder

You > /skills
  可用 Skill：
    code-review            代码审查。当用户要求审查代码...
    python-dev             Python 开发。当用户需要编写...
    data-analyst           数据分析。当用户需要分析数据...

You > 帮我写一个读取 CSV 的 Python 函数
  [工具调用] use_skill({'name': 'python-dev'})   ← Agent 自动判断调用 Skill
  [✓ 结果] # Skill: python-dev ...
Assistant : 好的，这里是一个读取 CSV 的函数...

You > /code-review                                 ← 用户手动触发 Skill
  [工具调用] ...
```

---

## 六、Web UI 操作手册

启动后访问 `http://localhost:8000`。

### 界面布局

```
┌──────────┬──────────────────────┬────────────────┐
│  侧边栏   │       对话区          │   配置编辑器    │
│  (220px) │       (可变宽)        │   (360px)      │
├──────────┤                      │                │
│ Sessions │                      │  点击侧边栏的   │
│ Skills   │  消息气泡             │  skill/persona  │
│ Personas │  工具调用折叠显示      │  自动打开编辑   │
│          │  输入框 + 发送        │                │
└──────────┴──────────────────────┴────────────────┘
```

### 新建会话

1. 点击侧边栏顶部 **"+ 新建"** 按钮
2. 选择 **Provider**（来自 config.yaml）
3. 选择 **Persona**（可选，推荐选一个）
4. 点击 **创建**

> Persona 决定 Agent 的 system prompt 和可用工具。Skills 在会话创建后自动可用，无需单独配置。

### 查看和编辑配置文件

- 侧边栏点击 **Skill 名称** → 右侧打开该 Skill 的 SKILL.md 编辑器
- 侧边栏点击 **Persona 名称** → 打开新建会话弹窗（预选该 Persona）
- 侧边栏右上角 **⚙** → 打开 config.yaml 编辑器

编辑完成后点 **保存**，修改立即生效（新会话生效，已有会话不受影响）。

### 对话操作

| 操作             | 方式                               |
| ---------------- | ---------------------------------- |
| 发送消息         | Enter 或点击发送按钮               |
| 换行             | Shift+Enter                        |
| 停止 Agent       | 点击 **停止** 按钮（发送取消信号） |
| 查看工具调用详情 | 点击 🔧 折叠块展开                 |
| 切换会话         | 点击侧边栏 Sessions 列表中的条目   |
| 删除会话         | 鼠标悬停在会话条目上，点击右侧 ×   |

---

## 七、提问模式（Stage 4）— AI 主动澄清模糊需求

> **核心思想**：把"AI 是不是应该问你问题"做成一个**会话级开关**。在需求清晰时，AI 直接执行；在需求模糊时，AI 会主动问你。
>
> **架构模型：deterministic interruptible agent runtime**。
> ask_user 是一个**非阻塞**工具——它立即返回一个占位结果，引擎在下一轮 loop 边界暂停，WebSocket 把 `question.asked` 推给前端，用户回复或跳过，引擎改写占位 tool_result 并恢复 loop。**tool ≠ execution blocker**；**engine = single source of truth**；**event-driven UI sync**。

### 7.1 两种模式

| 模式                               | 行为                                                              | 适用场景                          |
| ---------------------------------- | ----------------------------------------------------------------- | --------------------------------- |
| **直接执行**（`noquestion`，默认） | AI 基于合理假设直接执行，并在最终回答中**显式说明**做过的关键假设 | 你只是想要结果，不希望被反问      |
| **允许提问**（`question`）         | AI 在需求缺少会影响结果的关键信息时主动提问，提供 2–5 个互斥选项  | 复杂/模糊的需求，避免 AI 走偏方向 |

**最多一轮澄清**——避免连环追问；如果你想继续讨论，可以主动回复 AI。

### 7.2 谁来决定要不要问：LLM 决策层

决定"是否问"的是 **LLM 本身**，不是引擎、不是前端、不是任何 heuristic：

- 当 `question_mode == "question"` 时，`ask_user` 工具被注册到工具列表中，模型被显式告知它有"主动询问"的能力与契约。
- 引擎**不强制**模型提问；它**不会**在每轮插入"你应该问吗"之类的 hook。
- 前端**不参与**触发逻辑；它只在收到 `question.asked` 事件后渲染 UI。

系统提示（注入到每次 `question` 会话的 system prompt）显式声明：

```
## Question Mode (LLM decision layer)
This session has Question Mode enabled. The decision of WHETHER to
ask the user lives entirely in this LLM (the model). The engine does
not force you to ask; the frontend does not decide for you. You are
responsible for the decision.
```

ask_user 的 tool description 也明确写了：**"This tool is the DECISION-LAYER primitive: the model decides autonomously whether to call it."**

### 7.3 切换方式

**Web UI**：在输入框上方的工具条上点击"允许提问 / 直接执行"两个按钮，会立即生效并持久化到会话存储。

**REST API**：

```bash
# 切换到提问模式
curl -X PATCH http://localhost:8000/sessions/{session_id}/mode \
  -H "Content-Type: application/json" \
  -d '{"question_mode": "question"}'

# 切回直接执行
curl -X PATCH http://localhost:8000/sessions/{session_id}/mode \
  -H "Content-Type: application/json" \
  -d '{"question_mode": "noquestion"}'
```

**CLI**：

```bash
python cli.py --persona coder --question-mode question
```

### 7.4 运行时执行流（interrupt model）

```
LLM                  tool_executor          engine                   frontend
 │  tool_call(ask_user, questions)                │                          │
 │ ─────────────────▶│                          │                          │
 │                   │ validate + register_question_request                  │
 │                   │ ────────────────────────▶│                          │
 │                   │                          │ emit question.asked      │
 │                   │                          │ ───WS───────────────────▶│ render UI
 │  tool_result{is_interrupt=true, placeholder}   │                          │
 │ ◀─────────────────│                          │                          │
 │ engine sees is_interrupt → raises InterruptSignal                         │
 │                   │                          │ catches → WAITING_INTERRUPT│
 │                   │                          │ (loop parked)            │
 │        ... user types answer ...              │                          │
 │                                              │ ◀──── POST /reply ───────│
 │                                              │ rewrite placeholder      │
 │                                              │ emit question.resolved   │
 │                                              │ transition RUNNING       │
 │                                              │ _run_loop_guarded()      │
 │  next tool_result{real text}  ◀──────────────│                          │
 │ loop continues, LLM produces real answer      │                          │
```

关键点：

- **ask_user 不阻塞**——它在毫秒内返回 `InterruptibleToolResult`。
- **暂停发生在 engine 层**——`ReactLoop` 检测到 `is_interrupt=True`，抛 `InterruptSignal`，`AgentEngine._run_loop_guarded` 捕获并转换到 `WAITING_INTERRUPT`。
- **resume 来自外部事件**——`/reply` 或 `/reject` 触发改写 + 重启 loop。
- **对话始终有效**——assistant(tool_call) 和 tool(placeholder) 配对，validate_message_sequence 通过。改写后变成 assistant(tool_call) 和 tool(answer)，同样有效。

### 7.5 WebSocket 事件 schema

事件通道是**主路径**，GET /state 是**回退 / 快照恢复**。

| 事件                | 何时                                      | data 形状                            | 前端响应                 |
| ------------------- | ----------------------------------------- | ------------------------------------ | ------------------------ |
| `state`             | 引擎状态转换                              | `{status, is_running, ...}`          | 一般刷新                 |
| `question.asked`    | 引擎注册新 QuestionRequest                | `QuestionRequest` 完整 dict          | 立即渲染问题卡（不轮询） |
| `question.updated`  | 状态变化（intermediate）                  | `{request_id, status}`               | 局部刷新                 |
| `question.resolved` | 终端状态（answered / rejected / expired） | `{request_id, status, tool_call_id}` | 切到只读、等待下一轮 LLM |

完整 WS 协议（`api/ws.py` 顶部注释）：

```typescript
// server → client
{"type": "token",            "data": "<chunk>"}
{"type": "thinking"}
{"type": "thinking_token",   "data": "<chunk>"}
{"type": "message",          "data": <serialized Message>}
{"type": "state",            "data": <snapshot>}
{"type": "question.asked",   "data": <QuestionRequest>}
{"type": "question.updated", "data": {request_id, status}}
{"type": "question.resolved","data": {request_id, status, tool_call_id}}
{"type": "error",            "data": {detail}}
```

### 7.6 ask_user 工具：input 契约

`ask_user` 在 Question Mode 开启时注册。它一次可以提出 **1–5 个结构化问题**，每个问题有：

- 2–5 个可选项（`label` + 可选 `description`）
- `multiple: false` = 单选，`true` = 多选
- `custom: true` = 允许用户输入自定义答案
- `header` = 短标题（可选）

LLM 看到的 tool input：

```json
{
  "questions": [
    {
      "question": "你想制作哪一类网站？",
      "header": "网站类型",
      "options": [
        { "label": "企业官网", "description": "展示公司、服务、联系方式" },
        { "label": "作品集网站", "description": "个人作品、案例展示" },
        { "label": "电商网站", "description": "需要商品、购物车、支付等" },
        { "label": "Landing Page", "description": "营销转化页面 · Recommended" }
      ],
      "multiple": false,
      "custom": true
    },
    {
      "question": "你希望网站包含哪些功能？",
      "header": "核心功能",
      "options": [
        { "label": "首页" },
        { "label": "关于我们" },
        { "label": "产品/服务展示" },
        { "label": "联系表单" },
        { "label": "后台管理" },
        { "label": "登录注册" }
      ],
      "multiple": true,
      "custom": true
    }
  ]
}
```

工具不接收 `_tool_call_id` 入参；这是 executor 注入的保留 kwarg（用于让引擎把占位 tool_result 改写成真答案）。

### 7.7 REST API

```bash
# 用户提交答案
curl -X POST $BASE/sessions/$SID/questions/$RID/reply \
  -H 'Content-Type: application/json' \
  -d '{"answers": [["企业官网"], ["首页","联系表单","自定义功能"]]}'

# 用户跳过/拒绝
curl -X POST $BASE/sessions/$SID/questions/$RID/reject
```

**数据校验规则**（后端强制）：

- `answers.length == questions.length`
- 单选（`multiple=false`）：每条 answer 最多 1 个
- 多选（`multiple=true`）：最多 `options.length + 1`（预留 1 个 custom）
- `custom=false`：每个 label 必须命中某个 option.label
- `custom=true`：最多 1 个自定义文本 + 若干已选 option
- 已 answered / rejected / expired 的 request 不能再次提交（返回 400 / 404）

### 7.8 状态机

```
              ┌─────────────┐
              │   pending   │  ← engine.register_question_request
              └──────┬──────┘
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
  ┌─────────┐  ┌──────────┐  ┌──────────┐
  │answered │  │ rejected │  │ expired  │
  └─────────┘  └──────────┘  └──────────┘
       submit_      reject_     cancel() or
       reply()      question()  loop timeout
```

**不可逆**——一旦转出 pending，永远不会回到 pending。**幂等**——重复 reply/reject 返回明确错误，不会覆盖已写入的答案。

### 7.9 程序化 API（Python）

```python
from harness.types.questions import QuestionPrompt, QuestionOption

# 1) 注册一个多问题请求（ask_user tool 内部调用此方法）
prompts = [
    QuestionPrompt(
        question="网站类型？",
        header="网站类型",
        options=[QuestionOption(label="A"), QuestionOption(label="B")],
    ),
    QuestionPrompt(
        question="核心功能？",
        options=[QuestionOption(label="X"), QuestionOption(label="Y")],
        multiple=True, custom=True,
    ),
]
await engine.register_question_request(
    request_id="req-1", tool_call_id="tc-1", questions=prompts,
)

# 2) 用户提交答案（REST /reply 走同一路径）
result = await engine.submit_question_reply(
    "req-1", [["A"], ["X", "Y", "free text"]],
)
# result = {"ok": True, "status": "answered", "answers": [...], "tool_call_id": "..."}

# 3) 用户拒绝
await engine.reject_question("req-1")
# result = {"ok": True, "status": "rejected"}

# 4) 取消整轮（expire 所有 pending）
await engine.cancel()

# 5) 监听 WS 事件（用于自建前端 / 测试）
async def listener(event):
    print(event["type"], event["data"])
engine.add_event_listener(listener)
```

### 7.10 职责边界

| 层                   | 职责                                                                                 | 禁止                            |
| -------------------- | ------------------------------------------------------------------------------------ | ------------------------------- |
| **LLM（决策层）**    | 决定是否调用 ask_user；构造 questions                                                | —                               |
| **Tool (ask_user)**  | 校验 schema；调用 engine.register_question_request；立即返回 InterruptibleToolResult | 拥有状态、阻塞执行、轮询        |
| **Engine**           | 单一状态所有者；管理 WAITING_INTERRUPT；改写占位 tool_result；emit WS 事件           | 替代 LLM 决定"该问什么"         |
| **Loop (ReactLoop)** | 检测 is_interrupt 标志，抛 InterruptSignal                                           | 等待用户、持有状态              |
| **REST**             | 校验输入；调用 engine 的 submit/reject 方法                                          | 直接改 messages、直接 emit 事件 |
| **WebSocket**        | 透传 engine 的事件帧                                                                 | 改状态、决定何时该问            |
| **Frontend**         | 监听 question.asked 渲染 UI；点 submit → POST /reply                                 | 控制 LLM 决策、轮询触发         |

### 7.11 何时使用哪种模式

- **你很清楚要什么** → 直接执行模式（默认），避免无谓的来回
- **需求复杂、可能漏说关键信息** → 允许提问模式，让 AI 主动暴露歧义
- **想保护自己的时间** → 两种都可以——AI 不会问无关紧要的问题

---

## 八、config.yaml 参数说明

```yaml
# ── Provider 配置 ──────────────────────────────────
default_provider: bltcy-anthropic # 默认使用的 provider

providers:
  bltcy-anthropic:
    name: anthropic
    model: claude-sonnet-4-6
    api_key: "${ANTHROPIC_API_KEY}" # 从环境变量读取
    max_tokens: 8192
    temperature: 0.0
    extra:
      thinking:
        enabled: false # Anthropic 扩展思考

  bltcy-openai:
    name: openai
    model: gpt-4o
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://..." # OpenAI 兼容接口填这里

# ── 引擎配置 ───────────────────────────────────────
engine:
  max_rounds: 50 # 单次对话最多 50 轮工具调用

# ── 上下文压缩 ─────────────────────────────────────
compression:
  token_window: 128000 # token 上限
  auto_trigger_ratio: 0.65 # 达到 65% 时触发自动压缩
  micro_keep_recent: 6 # Micro 压缩保留最近 N 轮完整
  summary_provider: bltcy-mini # 做摘要用的（便宜）模型

# ── 存储 ───────────────────────────────────────────
storage:
  backend: sqlite # sqlite（持久化）或 memory（重启丢失）
  path: ./harness.db # SQLite 文件路径

# ── 工具配置 ───────────────────────────────────────
tools:
  enabled: # 全局工具白名单
    - read_file # 注释掉某行 = 全局禁用该工具
    - search
    - shell # 高风险，可注释禁用

  limits: # 各工具输出字符上限
    read_file: 20000
    search: 10000
    shell: 15000
```

### 各设置效果说明

| 设置                                     | 效果                                               |
| ---------------------------------------- | -------------------------------------------------- |
| `tools.enabled` 注释掉 `shell`           | 所有 Persona 和 Skill 均无法使用 shell 工具        |
| Persona `allowed_tools` 只有 `read_file` | 该 Persona 创建的 Session 只能用 read_file         |
| `compression.auto_trigger_ratio: 0.5`    | 更激进地压缩（对话更长、更省 token，但摘要有损失） |
| `engine.max_rounds: 10`                  | 每次对话最多 10 轮工具调用，防止失控               |
| `storage.backend: memory`                | 重启后所有会话历史丢失（适合开发测试）             |

---

## 常见问题

**Q: Skill 没有被 Agent 自动调用？**

- 检查 SKILL.md 的 `description` 是否清晰描述了使用场景
- 可以用 `/code-review` 手动触发测试
- 确认 Skill 文件夹包含 `SKILL.md`（不是 `skill.md`，大小写敏感）

**Q: 创建 Session 时报 "Provider not found"？**

- 检查 `config.yaml` 中 `providers` 下的名称
- 检查对应的 API Key 环境变量是否已设置

**Q: SQLite 文件在哪里？**

- 默认路径：`./harness.db`（即启动 uvicorn 的工作目录下）
- 可在 `config.yaml` 的 `storage.path` 修改

**Q: 如何完全禁用工具权限，只让 Agent 对话？**

- 在 Persona 的 `allowed_tools` 中填空列表：`allowed_tools: []`
- 或在 `config.yaml` 把 `tools.enabled` 全部注释掉
