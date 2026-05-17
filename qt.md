# 组员 A 开发记录

## 一、文件操作

### `write_file`

- 文件：`harness/tools/builtin/write_file.py`
- 功能：写入或追加文件内容，自动创建父目录
- 参数：`path`、`content`、`append`（可选，默认 false）
- 错误处理：权限拒绝、读写异常均返回 `"Error: ..."` 字符串

### `edit_file`

- 文件：`harness/tools/builtin/edit_file.py`
- 功能：精确替换文件中的一段字符串，不支持整文件覆盖
- 参数：`path`、`old_string`、`new_string`、`replace_all`（可选）
- 关键逻辑：
  - `old_string` 出现 0 次 → 报错 `"Error: old_string not found..."`
  - 出现多次但未设 `replace_all=true` → 报错并告知出现次数
  - `replace_all=true` → 全局替换
  - 否则只替换第一个

---

## 二、Web 工具

### 依赖

`httpx>=0.27` 已加入 `pyproject.toml` 主依赖。

### `web_fetch`

- 文件：`harness/tools/builtin/web_fetch.py`
- 功能：抓取 URL 内容，去掉 HTML 标签返回纯文本
- 参数：`url`、`max_length`（可选，默认 8000）
- 处理步骤：去除 `<script>`、`<style>`、所有 HTML 标签、HTML 实体字符，折叠多余空白
- 超长自动截断并注明省略字数
- `config.yaml` limits：8000

### `web_search`

- 文件：`harness/tools/builtin/web_search.py`
- 功能：用 DuckDuckGo HTML 端点搜索，无需 API Key
- 参数：`query`、`max_results`（可选，默认 5）
- 实现：POST 到 `https://html.duckduckgo.com/html/`，正则解析标题+链接+摘要
- 未找到结果返回 `"No results found."`

---

## 三、规划工作流

### `think`

- 文件：`harness/tools/builtin/think_tool.py`
- 功能：让 Agent 在行动前输出推理过程，工具本身不做任何事，原样返回 thought 内容
- 参数：`thought`

### `todo_write`

- 文件：`harness/tools/builtin/todo_tool.py`
- 功能：会话级任务清单，存在内存 dict 里（key 是 `session_id`）
- 参数：`session_id`、`action`、`todos`（可选）、`index`（可选）、`status`（可选）
- `action` 逻辑：
  - `set`：初始化任务列表（`todos` 必填，格式 `[{content, status}]`）
  - `get`：列出当前所有任务
  - `update`：按 `index` 更新状态（`pending / in_progress / completed`）
- `config.yaml` limits：5000

---

## 四、注册位置

所有工具均注册到以下 3 处：

| 文件                                | 位置                                  |
| ----------------------------------- | ------------------------------------- |
| `harness/tools/builtin/__init__.py` | import + `__all__`                    |
| `harness/factory.py`                | import + `ALL_TOOLS` 字典             |
| `config.yaml`                       | `tools.enabled` 列表 + `tools.limits` |

---

## 五、测试

- 测试文件：`tests/test_tools.py`（追加）
- 运行结果：**20/20 通过**
- 覆盖：新工具 100% 覆盖，包含正常路径、边界情况和错误处理

| 工具         | 测试用例                                             |
| ------------ | ---------------------------------------------------- |
| `write_file` | 覆盖写入、追加、自动创建父目录、无效路径             |
| `edit_file`  | 覆盖替换、全量替换、重复报错、文件不存在、内容不匹配 |
| `think_tool` | 覆盖返回原内容、空字符串                             |
| `todo_write` | 覆盖 set/get/update、无效 status、get 空列表         |
| `web_fetch`  | smoke test、截断测试、无效 URL                       |
| `web_search` | smoke test                                           |

---

## 六、其他改动

- `pyproject.toml`：将 `httpx>=0.27` 从可选依赖移入主依赖
