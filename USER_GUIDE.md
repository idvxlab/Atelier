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
7. [config.yaml 参数说明](#七configyaml-参数说明)

---

## 一、快速启动

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动 Web 服务（推荐）
uvicorn api.rest:app --reload --port 8000
# 浏览器打开 http://localhost:8000

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

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ✓ | 文件路径 |
| `offset` | integer | — | 起始行（从 0 计，默认 0） |
| `limit` | integer | — | 读取行数上限 |

- 输出上限：**20,000 字符**（超出自动存入引用，Agent 可按需读取）
- 典型用途：读源代码、日志文件、配置文件

---

### `search` — 正则搜索

在文件或目录中搜索匹配行，返回 `文件名:行号: 内容` 格式。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pattern` | string | ✓ | 正则表达式或字面字符串 |
| `path` | string | ✓ | 文件或目录路径 |
| `case_sensitive` | boolean | — | 是否大小写敏感（默认 true） |
| `max_results` | integer | — | 最多返回行数（默认 100） |

- 输出上限：**10,000 字符**
- 典型用途：在代码库中搜索函数、变量、错误信息

---

### `shell` — 执行命令

执行系统命令，返回 stdout + stderr 合并输出。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `command` | array | ✓ | 命令和参数数组，如 `["ls", "-la"]` |
| `cwd` | string | — | 工作目录（默认 `.`） |
| `timeout` | number | — | 超时秒数（默认 30） |

- 输出上限：**15,000 字符**
- 安全：内部使用 `subprocess_exec`（非 shell=True），防止命令注入
- 如需禁用：在 `config.yaml` 的 `tools.enabled` 中注释掉 `shell` 行

---

### `use_skill` — 加载 Skill

加载指定 Skill 的详细说明，Agent 在判断任务匹配时自动调用（也可手动调用）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✓ | Skill 名称，如 `code-review`、`python-dev` |

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

| 字段 | 说明 |
|------|------|
| `name` | Persona 标识（即文件名，不带 .md） |
| `description` | 一句话描述，显示在前端和 CLI 列表里 |
| `allowed_tools` | 允许使用的工具列表；省略 = 使用 config.yaml 的全局设置 |
| `provider` | 可选，覆盖默认 provider |
| 正文（---之后）| System Prompt 内容，直接定义 Agent 的角色和行为 |

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

| 字段 | 说明 |
|------|------|
| `name` | Skill 标识（一般与文件夹名一致） |
| `description` | **关键**：Agent 靠这句话判断何时使用该 Skill |
| `disable-model-invocation` | `true` = Agent 不自动调用，只能用户手动 `/skill-name` 触发 |
| 正文（---之后）| Skill 的详细执行说明，调用时才加载 |

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

| 命令 | 说明 |
|------|------|
| `/exit` 或 `/quit` | 退出 |
| `/reset` | 开启新会话（保留当前 Persona 和工具配置） |
| `/tools` | 列出当前会话可用的工具 |
| `/skills` | 列出所有可用 Skill（及描述） |
| `/personas` | 列出所有可用 Persona（及描述） |
| `/state` | 显示引擎当前状态和消息数量 |
| `/<skill-name>` | 手动调用某个 Skill，如 `/code-review` |

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

| 操作 | 方式 |
|------|------|
| 发送消息 | Enter 或点击发送按钮 |
| 换行 | Shift+Enter |
| 停止 Agent | 点击 **停止** 按钮（发送取消信号） |
| 查看工具调用详情 | 点击 🔧 折叠块展开 |
| 切换会话 | 点击侧边栏 Sessions 列表中的条目 |
| 删除会话 | 鼠标悬停在会话条目上，点击右侧 × |

---

## 七、config.yaml 参数说明

```yaml
# ── Provider 配置 ──────────────────────────────────
default_provider: bltcy-anthropic   # 默认使用的 provider

providers:
  bltcy-anthropic:
    name: anthropic
    model: claude-sonnet-4-6
    api_key: "${ANTHROPIC_API_KEY}"   # 从环境变量读取
    max_tokens: 8192
    temperature: 0.0
    extra:
      thinking:
        enabled: false                # Anthropic 扩展思考

  bltcy-openai:
    name: openai
    model: gpt-4o
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://..."           # OpenAI 兼容接口填这里

# ── 引擎配置 ───────────────────────────────────────
engine:
  max_rounds: 50                      # 单次对话最多 50 轮工具调用

# ── 上下文压缩 ─────────────────────────────────────
compression:
  token_window: 128000                # token 上限
  auto_trigger_ratio: 0.65            # 达到 65% 时触发自动压缩
  micro_keep_recent: 6                # Micro 压缩保留最近 N 轮完整
  summary_provider: bltcy-mini        # 做摘要用的（便宜）模型

# ── 存储 ───────────────────────────────────────────
storage:
  backend: sqlite                     # sqlite（持久化）或 memory（重启丢失）
  path: ./harness.db                  # SQLite 文件路径

# ── 工具配置 ───────────────────────────────────────
tools:
  enabled:                            # 全局工具白名单
    - read_file                       # 注释掉某行 = 全局禁用该工具
    - search
    - shell                           # 高风险，可注释禁用

  limits:                             # 各工具输出字符上限
    read_file: 20000
    search:    10000
    shell:     15000
```

### 各设置效果说明

| 设置 | 效果 |
|------|------|
| `tools.enabled` 注释掉 `shell` | 所有 Persona 和 Skill 均无法使用 shell 工具 |
| Persona `allowed_tools` 只有 `read_file` | 该 Persona 创建的 Session 只能用 read_file |
| `compression.auto_trigger_ratio: 0.5` | 更激进地压缩（对话更长、更省 token，但摘要有损失） |
| `engine.max_rounds: 10` | 每次对话最多 10 轮工具调用，防止失控 |
| `storage.backend: memory` | 重启后所有会话历史丢失（适合开发测试） |

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
