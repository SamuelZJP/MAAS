# 语义记忆模块（Semantic Memory）

## 1. 概述

语义记忆模块管理角色对话中的"变量"性质记忆——好感度、人际关系、服装状态、当前时间地点等。每个角色拥有独立的 Schema 定义，语义记忆在每个对话回合后更新并存储完整快照。

召回时全量返回，归档时由 LLM 通过 JSON Patch 指令更新。

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| Schema | 角色专属的 Pydantic 模型定义，描述该角色语义记忆的结构、默认值和校验规则，手动编码维护 |
| 快照（Snapshot） | 某一回合结束时语义记忆的完整 JSON 状态，每轮存储一份 |
| JSON Patch | LLM 输出的变量更新指令（RFC 6902 子集），用于在现有快照上执行增量修改 |

---

## 3. Schema 定义

### 3.1 存储位置

每个角色的 Schema 以 Python 文件形式存放：

```
data/{chat_id}.py
```

`chat_id` 即角色名，与文件名一一对应。

### 3.2 文件内容

每个 Schema 文件导出一个 Pydantic 模型类，需支持：

- 字段默认值：用于初始化时生成 round_id=0 的基线快照
- 校验与 transform 规则：通过 `@model_validator` / `@field_validator` 实现业务逻辑约束（如好感度不足时自动降级关系）
- 序列化为 JSON：用于数据库存储
- 序列化为 YAML：用于 LLM 提示词中的可读展示

### 3.3 示例

```python
# data/苏菲.py
from pydantic import BaseModel, model_validator

class 世界(BaseModel):
    日期: str = "YYYY-MM-DD 星期X"
    时间: str = "HH:MM"
    地点: str = "未知地点"

class 情感(BaseModel):
    好感度: int = 0
    爱意值: int = 0
    当前关系: str = "陌生"

class 服装(BaseModel):
    外套: str = "无"
    上衣: str = "无"
    下装: str = "无"
    内衣: str = "无"
    内裤: str = "无"
    袜子: str = "无"
    鞋子: str = "无"
    配饰: str = "无"

class 苏菲(BaseModel):
    情感: 情感 = 情感()
    服装: 服装 = 服装()
    姿势: str = "无"
    想法: str = "无"

    @model_validator(mode="after")
    def enforce_relationship_rules(self):
        e = self.情感
        e.好感度 = max(0, min(100, e.好感度))
        e.爱意值 = max(0, min(100, e.爱意值))

        if e.好感度 < 100 and e.当前关系 in ("情侣", "夫妻"):
            e.当前关系 = "师生"
        if e.当前关系 not in ("情侣", "夫妻"):
            e.爱意值 = 0
        if e.当前关系 == "夫妻" and e.爱意值 < 100:
            e.当前关系 = "情侣"
        return self

class Schema(BaseModel):
    世界: 世界 = 世界()
    苏菲: 苏菲 = 苏菲()
```

---

## 4. 数据模型

### 4.1 semantic_memories

| 字段 | 类型 | 说明 |
|------|------|------|
| chat_id | string, FK → chats | 所属角色 |
| round_id | integer | 对应回合序号；0 表示初始基线 |
| content | text (JSON) | 该回合结束时的完整语义记忆快照 |
| created_at | datetime | 记录创建时间 |

主键：(chat_id, round_id)

### 4.2 与现有模型的关系

- `semantic_memories.chat_id` 引用 `chats.chat_id`
- `semantic_memories.round_id = 0` 为初始化生成的基线记录，不对应 rounds 表中的任何回合
- `semantic_memories.round_id >= 1` 与 `rounds.round_id` 一一对应

---

## 5. 模块启用

在 `POST /chats` 中，将 `"semantic"` 加入 `enabled_modules`：

```json
{
  "enabled_modules": ["episodic", "semantic"]
}
```

初始化时（`POST /chats`），若 `enabled_modules` 包含 `"semantic"`，系统加载 `data/{chat_id}.py` 中的 Schema，以默认值生成 round_id=0 的基线快照并写入 `semantic_memories`。

已初始化的 chat 不允许通过 `PATCH /chats/{chat_id}` 中途新增或移除 `"semantic"`。

---

## 6. 召回流程

语义记忆在 `POST /recall` 编排流程中被调用。

```
检查 semantic 模块是否启用
若未启用 → 跳过
      │
      ▼
从 semantic_memories 表读取当前 chat 的最新快照
（round_id 最大的那条记录）
      │
      ▼
将 JSON 内容直接返回
```

响应中新增 `semantic_memory` 字段：

```json
{
  "recalled_episodes": [...],
  "semantic_memory": {
    "世界": { "日期": "2026-04-08 星期三", "时间": "14:30", "地点": "教室" },
    "苏菲": { "情感": { "好感度": 45, ... }, ... }
  }
}
```

前端可直接读取该对象。

---

## 7. 归档流程

语义记忆在 `POST /archive` 编排流程中被调用，与 episodic 模块并行（互不依赖）。

```
检查 semantic 模块是否启用
若未启用 → 跳过
      │
      ▼
读取当前最新快照（上一轮的语义记忆）
      │
      ▼
将快照转换为 YAML 格式（供 LLM 阅读）
      │
      ▼
┌─ LLM 调用：语义记忆更新 ────────────────┐
│ 输入：当前语义记忆（YAML）                │
│      + 本回合 user_input + ai_response   │
│      + context.extra                     │
│ 输出：JSON Patch 指令                     │
└──────────────────────────────────────────┘
      │
      ▼
将 JSON Patch 应用到当前快照上
（单条 patch 出错则跳过该条，继续执行剩余 patch）
      │
      ▼
用 Schema 对更新后的对象做校验和 transform
      │
      ▼
将校验后的完整对象作为新快照存入 semantic_memories
（chat_id + 本回合 round_id）
      │
      ▼
返回 { semantic_updated: true, semantic_memory: {...} }
```

若 LLM 返回非法内容、Patch 全部失败、Schema 校验失败或其他语义模块内部错误，则不影响本轮 `rounds` 写入与其他模块归档；系统直接沿用上一回合（n-1）的完整快照，写入当前回合（n）的 `semantic_memories`，并返回 `semantic_updated: false`。

---

## 8. 回滚对接

### 8.1 触发条件

与系统回滚机制一致：`POST /recall` 中检测到 `latest_round_id < DB 中 max(round_id)` 时触发。

### 8.2 回滚操作

设回滚点为 `R = latest_round_id`：

1. 删除 `semantic_memories` 中 `round_id > R` 的所有记录
2. 当前语义记忆状态自动回退为 round_id = R 的快照（若 R = 0 则回到初始基线）

无需额外处理，快照式存储天然支持回滚。

---

## 9. LLM 提示词模板

### 9.1 归档：语义记忆更新

```
你是一个记忆管理助手。请根据最新的对话内容，判断哪些语义记忆变量需要更新。

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
- 使用 JSON Patch 格式（仅支持 replace / add / remove 操作）
- path 使用 JSON Pointer 语法（如 "/苏菲/情感/好感度"）
- 若无任何变化，输出空数组

## 输出格式
仅输出 JSON Patch 数组，示例：
[
  { "op": "replace", "path": "/世界/时间", "value": "15:00" },
  { "op": "replace", "path": "/苏菲/情感/好感度", "value": 50 }
]
若无变化：[]
```

---

## 10. CRUD API

以下接口均属于 `admin.py` 调试/管理接口。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /chats/{chat_id}/semantic | 获取最新语义记忆快照 |
| GET | /chats/{chat_id}/semantic/{round_id} | 获取指定回合的语义记忆快照 |
| GET | /chats/{chat_id}/semantic/history | 获取所有快照列表（调试用） |
| PUT | /chats/{chat_id}/semantic/{round_id} | 覆写指定回合的语义记忆快照 |

---

## 11. 目录结构扩展

```
modules/
  semantic/
    __init__.py
    recall.py        # 召回逻辑（读取最新快照）
    archive.py       # 归档逻辑（LLM 调用 + patch 应用 + 校验）
    prompts.py       # 提示词模板
    schema_loader.py # 动态加载 data/{chat_id}.py 中的 Schema

data/
  苏菲.py            # 角色"苏菲"的语义记忆 Schema
  ...                # 其他角色
```

`repository/crud/` 下新增 `semantic.py` 处理 semantic_memories 表的读写。
