---
name: my-skill
description: "一句话说明这个 skill 的用途。Agent 用这段描述来判断何时自动调用它。"
# disable-model-invocation: true   # 取消注释 = 只能用户手动 /skill-name 调用，Agent 不会自动用
---

在这里写 skill 的详细执行说明。

这段内容只在 skill 被调用时才加载到上下文，不会一直占用 token。

## 示例结构

1. **背景** — 说明 agent 应处于什么场景下
2. **步骤** — 列出具体执行步骤
3. **输出格式** — 规定回答的格式和语言
