# MyHarnessPy 开发计划

三个人来推进这个项目。我负责核心引擎，你们两个人分别做下面的工具模块，这周全部完成。

---

## 先读这个：工具怎么写

每个工具 = 一个 Python 文件，里面两个东西：

```python
# 1. SCHEMA：告诉 LLM 工具名、参数
WRITE_FILE_SCHEMA = ToolSchema(
    name="write_file",
    description="Write content to a file.",
    params=[
        ToolParam("path", "string", "File path"),
        ToolParam("content", "string", "Content to write"),
        ToolParam("append", "boolean", "Append instead of overwrite", required=False),
    ],
)

# 2. handler：实际执行，参数名和 ToolParam.name 完全对应，永远返回字符串
async def write_file_tool(path: str, content: str, append: bool = False) -> str:
    ...
```

写完在三个地方注册，缺一不可：
- `harness/tools/builtin/__init__.py` — 导出
- `api/rest.py` 和 `cli.py` 的 `ALL_TOOLS` 字典 — 两个文件都加
- `config.yaml` 的 `tools.enabled` — 加工具名

两条规则：handler 必须是 `async def`；出错只返回 `"Error: ..."` 字符串，不要 raise。

参考现有代码：`harness/tools/builtin/read_file.py`、`shell.py`、`search.py`。

---

## 组员 A 的任务

文件操作 + Web + 规划工作流，这周全做完。

### 文件操作

`read_file` 已经有了，做下面两个。

**`write_file`** — 新建 `harness/tools/builtin/write_file.py`

写入或追加文件内容，自动创建父目录。参数：`path`、`content`、`append`（可选，默认 false）。

**`edit_file`** — 新建 `harness/tools/builtin/edit_file.py`

精确替换文件里的一段字符串，不能整文件覆盖。参数：`path`、`old_string`、`new_string`、`replace_all`（可选）。注意：`old_string` 在文件里出现多次时，未设 `replace_all=true` 应该报错。

### Web

先装依赖：`pip install httpx`

**`web_fetch`** — 新建 `harness/tools/builtin/web_fetch.py`

抓取 URL 内容，去掉 HTML 标签返回纯文本。参数：`url`、`max_length`（可选，默认 8000）。

**`web_search`** — 新建 `harness/tools/builtin/web_search.py`

用 DuckDuckGo 搜索，不需要 API Key，POST 到 `https://html.duckduckgo.com/html/`，从返回 HTML 里解析标题+链接+摘要。参数：`query`、`max_results`（可选，默认 5）。

### 规划工作流

**`think`** — 新建 `harness/tools/builtin/think_tool.py`

让 Agent 在行动前说出推理过程，工具本身不做任何事，原样返回 thought 内容。参数：`thought`。

**`todo_write`** — 新建 `harness/tools/builtin/todo_tool.py`

会话级任务清单，存在内存 dict 里（key 是 session_id）。参数：`session_id`、`action`（set/update/get）、`todos`（可选，action=set 时用）、`index`+`status`（可选，action=update 时用）。status 只有三个值：`pending`、`in_progress`、`completed`。

---

## 组员 B 的任务

搜索 + 执行 + MCP，这周全做完。

### 搜索

`search` 已经有了，可以跳过，也可以进一步优化

**`glob`** — 新建 `harness/tools/builtin/glob_tool.py`

按文件名模式查找文件，用 Python 的 `pathlib.Path.glob()` 实现，跨平台。参数：`pattern`（如 `**/*.py`）、`path`（可选，默认 `.`）、`max_results`（可选，默认 100）。

**`grep`** — 新建 `harness/tools/builtin/grep_tool.py`

带上下文行的内容搜索。参数：`pattern`、`path`、`context`（前后各 N 行，可选）、`before_context`、`after_context`（可选）、`case_sensitive`（可选）、`file_pattern`（只搜特定扩展名，可选）、`max_results`（可选，默认 50）。

### 执行

**改进 `shell`** — 修改 `harness/tools/builtin/shell.py`

当前实现把 stdout/stderr 合并了，看不到退出码。改成分离 stderr，返回格式加上 `[exit code: N]`。同时加 `env` 参数（dict，可选）允许注入额外环境变量。

**`powershell`** — 新建 `harness/tools/builtin/powershell_tool.py`

Windows 上调 `pwsh.exe`（找不到就用 `powershell.exe`），Linux/Mac 上调 `pwsh`。参数：`script`、`cwd`（可选）、`timeout`（可选，默认 30）。

### MCP 协议

MCP（Model Context Protocol）是标准协议，接入后 Agent 可以连任何 MCP Server 动态获取工具。分三步，新建 `harness/mcp/` 目录：

**`harness/mcp/stdio_transport.py`**

用 `asyncio.create_subprocess_exec` 启动 MCP Server 子进程，通过 stdin/stdout 收发 JSON-RPC 消息。

```python
class StdioTransport:
    async def start(self, command: list[str]) -> None: ...
    async def send(self, msg: dict) -> dict: ...
    async def close(self) -> None: ...
```

**`harness/mcp/client.py`**

封装协议细节，暴露干净的接口：

```python
class MCPClient:
    async def connect(self, command: list[str]) -> None: ...
    async def list_tools(self) -> list[ToolSchema]: ...
    async def call_tool(self, name: str, args: dict) -> str: ...
    async def close(self) -> None: ...
```

**`harness/mcp/bridge.py`**

把 MCP Server 的工具全部注册进 `ToolRegistry`：

```python
async def register_mcp_server(registry: ToolRegistry, client: MCPClient) -> list[str]:
    """返回注册的工具名列表"""
```

做完之后 `config.yaml` 可以这样配来启用：
```yaml
mcp_servers:
  filesystem:
    transport: stdio
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]
```

MCP 是最复杂的，遇到问题找我。

---

## 我的部分

- `harness/factory.py` — 把 cli.py 和 rest.py 里重复的 build_engine 合并（你们做工具不需要动这块）
- WebSocket 消息监听器 — 实时推送每条消息
- LLM 流式输出
- 审批流（危险命令暂停等确认）
- `spawn_agent` 工具（主 Agent 创建子 Agent）加上之后多agent的协作

---

## 快速查文件

| 想做的事 | 对应文件 |
|----------|----------|
| 新建工具 | `harness/tools/builtin/<name>.py` |
| 注册工具（三个地方都要改） | `__init__.py` + `api/rest.py` + `cli.py` |
| 启用工具 | `config.yaml` → `tools.enabled` |
| 工具参数类型定义 | `harness/types/tools.py` |
| 消息类型定义 | `harness/types/messages.py` |
| 现有工具参考 | `harness/tools/builtin/read_file.py` / `shell.py` |
| Persona 配置 | `personas/<name>.md` → `allowed_tools:` |
| 主循环 | `harness/engine/loop.py` |
| 配置解析 | `harness/config.py` |
