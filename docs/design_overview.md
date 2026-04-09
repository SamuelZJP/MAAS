# MAAS 设计文档 — 系统总述

## 1. 文档范围

本文档描述 MAAS 系统的整体架构、公共数据模型、核心 API 接口和跨模块机制。

各功能模块的详细设计（数据模型、流程、提示词等）见各模块目录下的文档：

- 情节记忆：`modules/episodic/README.md`

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| Chat | 一个角色的完整对话上下文，对应 SillyTavern 中的一张角色卡 |
| First Message | 角色的首条消息（第 0 楼），不属于任何对话回合，但可参与首个事件的归档 |
| Round（对话回合） | 一次用户输入 + 一次 AI 回复，是系统的最小记录单位，round_id 从 1 起递增 |
| Module（功能模块） | 可插拔的记忆处理单元，通过 `enabled_modules` 配置启用/禁用 |

---

## 3. 公共数据模型

### 3.1 chats

| 字段 | 类型 | 说明 |
|------|------|------|
| chat_id | string, PK | 角色/对话唯一标识，由前端提供 |
| first_message | text | 角色首条消息原文 |
| first_message_archived | boolean, default false | 首条消息是否已归入某个事件 |
| enabled_modules | JSON array, default [] | 已启用的模块列表，当前可选值：`"episodic"`、`"semantic"`；其中 `semantic` 只能在初始化时决定 |
| created_at | datetime | 记录创建时间 |

### 3.2 rounds

| 字段 | 类型 | 说明 |
|------|------|------|
| chat_id | string, FK → chats | 所属角色 |
| round_id | integer | 回合序号，同一 chat 内从 1 起递增 |
| user_input | text | 用户输入原文 |
| ai_response | text | AI 回复原文 |
| summary | text | 本回合的摘要（由 ST 前端提供，包含剧情时间） |
| episode_id | integer, nullable | 所归属的事件 ID；null 表示未归档 |
| created_at | datetime | 记录创建时间 |

主键：(chat_id, round_id)

---

## 4. API 设计

基础路径：`/api/v1`

### 4.1 Chat 管理

#### POST /chats — 初始化角色对话

请求体：
```json
{
  "chat_id": "char_alice_01",
  "first_message": "你好，我是Alice...",
  "enabled_modules": ["episodic", "semantic"]
}
```

响应 201：
```json
{
  "chat_id": "char_alice_01",
  "created_at": "2026-04-03T12:00:00Z"
}
```

#### GET /chats/{chat_id} — 获取角色对话配置

响应 200：完整 chats 记录

#### PATCH /chats/{chat_id} — 更新配置

请求体（部分更新）：
```json
{
  "enabled_modules": ["episodic", "semantic"]
}
```

说明：
- `semantic` 模块只能在 `POST /chats` 初始化时启用
- 已初始化的 chat 不允许通过 `PATCH /chats/{chat_id}` 新增或移除 `semantic`

#### DELETE /chats/{chat_id} — 删除角色对话及其所有关联数据

级联删除该 chat 下所有 rounds 和 episodes。

### 4.2 核心工作流 API

以下两个端点是 ST 前端在每次对话中调用的主入口。各模块在这两个端点内部被编排调用。

#### POST /recall — 记忆召回

**调用时机**：用户输入发送后、AI 生成前。

请求体：
```json
{
  "chat_id": "char_alice_01",
  "latest_round_id": 15,
  "recall_start_round_id": 3,
  "recall_end_round_id": 8,
  "context": {
    "user_input": "用户本轮的输入文本",
    "extra": "其他上下文信息（角色性格等，由前端硬编码提供）"
  }
}
```

字段说明：
- `latest_round_id`：前端计算的、本次用户输入**之前**的最新回合 ID。若为首次对话（尚无任何回合），传 0。
- `recall_start_round_id`：召回候选范围的起始回合 ID。需与 `recall_end_round_id` 同时提供。
- `recall_end_round_id`：召回候选范围的终止回合 ID。需与 `recall_start_round_id` 同时提供。
- 两者必须**同时提供**，后端才会执行情节记忆召回，将**与该回合区间有重叠**的 episodes 作为候选事件交给 LLM 筛选。若未同时提供，情节记忆模块不进行召回。
- `context.user_input`：用户本轮输入原文（尚未归档，后端 DB 中不存在）。
- `context.extra`：后端不持有的外部上下文（角色性格等），由前端硬编码提供。
- **近期对话上下文由后端自行组装**：后端根据全局配置 `recent_rounds_count` 从 rounds 表读取最近 N 轮摘要，无需前端传递。

响应 200：
```json
{
  "recalled_episodes": [
    {
      "episode_id": 3,
      "title": "初次见面的误会",
      "summary": "事件摘要文本..."
    }
  ],
  "semantic_memory": {
    "世界": {
      "日期": "2026-04-08 星期三",
      "时间": "14:30",
      "地点": "教室"
    }
  },
  "rollback_performed": false,
  "rollback_to_round_id": null
}
```

若无模块被启用或无可召回内容，`recalled_episodes` 为空数组，`semantic_memory` 为 `null`。

#### POST /archive — 记忆归档

**调用时机**：AI 回复后。

请求体：
```json
{
  "chat_id": "char_alice_01",
  "round_id": 16,
  "user_input": "用户输入原文",
  "ai_response": "AI回复原文",
  "summary": "本回合摘要（含剧情时间）",
  "context": {
    "extra": "角色性格等上下文（由前端硬编码提供）"
  }
}
```

响应 200：
```json
{
  "round_stored": true,
  "episode_created": false,
  "new_episode": null,
  "semantic_updated": false,
  "semantic_memory": {
    "世界": {
      "日期": "2026-04-08 星期三",
      "时间": "14:30",
      "地点": "教室"
    }
  }
}
```

若检测到事件边界并成功归档：
```json
{
  "round_stored": true,
  "episode_created": true,
  "semantic_updated": true,
  "semantic_memory": {
    "世界": {
      "日期": "2026-04-08 星期三",
      "时间": "15:00",
      "地点": "教室"
    }
  },
  "new_episode": {
    "episode_id": 5,
    "title": "新事件标题",
    "summary": "新事件摘要...",
    "start_round_id": 12,
    "end_round_id": 16
  }
}
```

### 4.3 管理/调试 CRUD API

#### Rounds

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /chats/{chat_id}/rounds | 获取该角色所有回合，支持查询参数 `archived=true/false` |
| GET | /chats/{chat_id}/rounds/{round_id} | 获取单个回合 |
| DELETE | /chats/{chat_id}/rounds/{round_id} | 删除单个回合（需处理关联事件） |

各模块的专属 CRUD API 见模块自身文档。

---

## 5. 回滚机制

### 5.1 触发条件

在召回流程的同步检查阶段，若 `latest_round_id < DB 中 max(round_id)`，说明前端（SillyTavern）有楼层被删除，后端数据需要回滚。

### 5.2 回滚操作

设回滚点为 `R = latest_round_id`，执行以下操作（在单个事务中）：

1. **识别受影响的 episodes**：查找所有 `start_round_id > R` 或 `end_round_id > R` 的 episodes

2. **处理受影响的 episodes**：
   - 若 episode 的 `start_round_id > R`：整个 episode 在回滚范围内，直接删除
   - 若 episode 的 `start_round_id <= R` 且 `end_round_id > R`：episode 被部分截断，由于其摘要是基于完整范围生成的，已不可信 → **删除该 episode**，将其范围内 `round_id <= R` 的 rounds 的 episode_id 重置为 null

3. **删除回滚范围内的 rounds**：删除所有 `round_id > R` 的 rounds

4. **删除回滚范围内的 semantic 快照**：删除 `semantic_memories` 中所有 `round_id > R` 的记录，使当前语义状态自动回退到回滚点快照

5. **处理 first_message 状态**：若被删除的 episode 中包含 episode_id = 1（首个事件），则将 `first_message_archived` 重置为 false

### 5.3 回滚后状态

回滚完成后，被波及的 rounds 恢复为未归档状态，将在后续归档流程中重新参与事件边界检测和摘要生成。

---

## 6. 全局配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| recent_rounds_count | integer | 10 | 召回时后端从 rounds 表读取的最近回合数，用于组装 LLM 上下文 |
| llm_endpoint | string | — | 外部 LLM API 地址 |
| llm_model | string | — | 使用的模型标识 |

首期以全局配置文件或环境变量形式管理即可，未来可迁移为角色级配置。

---

## 7. 扩展预留

以下设计点已为未来模块预留接口，当前不实现：

| 预留点 | 说明 |
|--------|------|
| enabled_modules | chats 表中的 JSON 数组，当前已支持 `"episodic"`、`"semantic"`，未来仍可继续扩展 `"working"`、`"personality"`、`"lore"` |
| /recall 响应结构 | 当前返回 `recalled_episodes`、`semantic_memory`，未来可继续扩展 `working_memory` 等字段 |
| /archive 响应结构 | 当前返回 episodic 与 semantic 的归档结果，未来可继续扩展其他模块结果 |
| context 字段 | 召回和归档请求中的 context 为开放结构，仅承载后端不持有的外部信息；未来模块所需上下文可自由扩展 |
| 情节记忆预筛选 | 当事件数量增长后，可在 LLM 筛选前接入向量检索做粗筛，API 接口无需变更 |

---

## 8. 技术备忘

- 数据库：首期使用 SQLite，足够支撑单用户原型场景，后续可迁移
- LLM 调用：通过 HTTP 请求外部 LLM API，需要可配置的 endpoint 和 model 参数
- 事务性：回滚操作必须在单个数据库事务中完成，确保数据一致性
- 幂等性：归档接口应处理重复 round_id 的情况（相同 chat_id + round_id 重复提交时，跳过或更新）
