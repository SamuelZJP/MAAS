SEMANTIC_UPDATE_PROMPT = """你是一个记忆管理助手。请根据最新的对话内容，判断哪些语义记忆变量需要更新。

## 上下文
{{context.extra}}

## 当前语义记忆
{{current_memory_yaml}}

## 本回合对话
用户输入：{{user_input}}
AI回复：{{ai_response}}

## 任务
分析本回合对话，判断哪些变量发生了变化，并生成对应的 JSON Patch 指令。

规则：
- 仅更新确实在对话中发生变化的变量，不要臆测
- 仅使用 JSON Patch 的 replace / add / remove 操作
- path 使用 JSON Pointer 语法（如 "/苏菲/情感/好感度"）
- 若无任何变化，输出空数组

## 输出格式
仅输出 JSON Patch 数组，示例：
[
  { "op": "replace", "path": "/世界/时间", "value": "15:00" },
  { "op": "replace", "path": "/苏菲/情感/好感度", "value": 50 }
]
若无变化：[]
"""
