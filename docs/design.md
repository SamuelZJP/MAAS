# MAAS 设计文档 v1 — 记忆仓库 + 情节记忆

## 1. 文档范围

本文档覆盖 MAAS 首期开发的两个子系统：

- **记忆仓库**：基础存储层，为所有模块提供数据持久化与 CRUD 能力
- **情节记忆**：基于事件的记忆归档与召回

其余模块（语义记忆、工作记忆、人格系统、背景信息）不在本期范围内，但数据模型和 API 设计为其预留扩展位。

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| Chat | 一个角色的完整对话上下文，对应 SillyTavern 中的一张角色卡 |
| First Message | 角色的首条消息（第 0 楼），不属于任何对话回合，但可参与首个事件的归档 |
| Round（对话回合） | 一次用户输入 + 一次 AI 回复，是系统的最小记录单位，round_id 从 1 起递增 |
| Episode（事件） | 一到多个连续对话回合的压缩产物，是记忆召回时的基本单位 |
| 事件边界 | 相邻回合之间剧情发生显著转折的位置 |

---

## 3. 数据模型

### 3.1 chats

| 字段 | 类型 | 说明 |
|------|------|------|
| chat_id | string, PK | 角色/对话唯一标识，由前端提供 |
| first_message | text | 角色首条消息原文 |
| first_message_archived | boolean, default false | 首条消息是否已归入某个事件 |
| enabled_modules | JSON array, default [] | 已启用的模块列表，当前可选值：`"episodic"` |
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

### 3.3 episodes

| 字段 | 类型 | 说明 |
|------|------|------|
| chat_id | string, FK → chats | 所属角色 |
| episode_id | integer | 事件序号，同一 chat 内从 1 起递增 |
| title | string | 事件标题（最浓缩信息） |
| summary | text | 事件级摘要（次浓缩信息） |
| start_round_id | integer | 事件覆盖的起始回合 ID |
| end_round_id | integer | 事件覆盖的终止回合 ID |
| created_at | datetime | 记录创建时间 |

主键：(chat_id, episode_id)

### 3.4 数据关系约束

- rounds.episode_id 引用同 chat 下 episodes.episode_id
- 一个 episode 覆盖 [start_round_id, end_round_id] 范围内的所有 rounds
- 方案 A 约束：每个 round 最多归属一个 episode（episode_id 为标量）

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
  "enabled_modules": ["episodic"]
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
  "enabled_modules": ["episodic"]
}
```

#### DELETE /chats/{chat_id} — 删除角色对话及其所有关联数据

级联删除该 chat 下所有 rounds 和 episodes。

---

### 4.2 核心工作流 API

以下两个端点是 ST 前端在每次对话中调用的主入口。

#### POST /recall — 记忆召回

**调用时机**：用户输入发送后、AI 生成前。

请求体：
```json
{
  "chat_id": "char_alice_01",
  "latest_round_id": 15,
  "context": {
    "user_input": "用户本轮的输入文本",
    "extra": "其他上下文信息（角色性格等，由前端硬编码提供）"
  }
}
```

字段说明：
- `latest_round_id`：前端计算的、本次用户输入**之前**的最新回合 ID。若为首次对话（尚无任何回合），传 0。
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
  "rollback_performed": false,
  "rollback_to_round_id": null
}
```

若无情节记忆模块启用或无事件存在，`recalled_episodes` 为空数组。

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
  "new_episode": null
}
```

若检测到事件边界并成功归档：
```json
{
  "round_stored": true,
  "episode_created": true,
  "new_episode": {
    "episode_id": 5,
    "title": "新事件标题",
    "summary": "新事件摘要...",
    "start_round_id": 12,
    "end_round_id": 16
  }
}
```

---

### 4.3 记忆仓库 CRUD API（管理/调试用）

这些端点主要服务于调试、运维和未来模块的直接数据访问需求。

#### Rounds

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /chats/{chat_id}/rounds | 获取该角色所有回合，支持查询参数 `archived=true/false` |
| GET | /chats/{chat_id}/rounds/{round_id} | 获取单个回合 |
| DELETE | /chats/{chat_id}/rounds/{round_id} | 删除单个回合（需处理关联事件） |

#### Episodes

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /chats/{chat_id}/episodes | 获取该角色所有事件 |
| GET | /chats/{chat_id}/episodes/{episode_id} | 获取单个事件详情 |
| DELETE | /chats/{chat_id}/episodes/{episode_id} | 删除单个事件（其下 rounds 的 episode_id 重置为 null） |

---

## 5. 核心流程详述

### 5.1 记忆召回流程

```
前端发起 POST /recall
        │
        ▼
  ┌─ 同步检查 ──────────────────────────────┐
  │ 读取 DB 中该 chat 的 max(round_id)       │
  │                                          │
  │ 若 latest_round_id < max(round_id)：     │
  │   执行回滚（见 §6）                       │
  │ 若 latest_round_id > max(round_id)：     │
  │   正常（说明有未归档的回合，不影响召回）    │
  │ 若相等：正常                              │
  └──────────────────────────────────────────┘
        │
        ▼
  检查 episodic 模块是否启用
  若未启用 → 返回空结果
        │
        ▼
  查询该 chat 所有 episodes → 提取 (episode_id, title) 列表
  若列表为空 → 返回空结果
        │
        ▼
  从 rounds 表读取最近 N 轮摘要（N = recent_rounds_count 全局配置）
        │
        ▼
  组装 LLM 请求（见 §7.1 召回提示词模板）
  输入：事件列表 + 近期回合摘要 + context（user_input, extra）
  输出：LLM 返回所需的 episode_id 列表
        │
        ▼
  根据返回的 episode_id 查询对应 episodes 的完整摘要
        │
        ▼
  返回 recalled_episodes
```

### 5.2 记忆归档流程

```
前端发起 POST /archive
        │
        ▼
  将本轮对话存入 rounds 表（episode_id = null）
        │
        ▼
  检查 episodic 模块是否启用
  若未启用 → 返回 { round_stored: true, episode_created: false }
        │
        ▼
  收集待处理内容：
    - 所有 episode_id 为 null 的 rounds（按 round_id 升序），提取其 summary
    - 若 first_message_archived 为 false，将 first_message 也纳入（置于最前）
        │
        ▼
  ┌─ LLM 调用 1：事件边界检测（见 §7.2） ───┐
  │ 输入：待处理回合的 summary 列表 + context  │
  │ 输出：是否存在事件边界 (boolean)           │
  │       若存在，返回边界位置（边界回合ID）     │
  └──────────────────────────────────────────┘
        │
   无边界 → 返回 { round_stored: true, episode_created: false }
        │
   有边界 ↓
        ▼
  确定归档范围：从最早的未归档回合到边界回合（含边界回合）
        │
        ▼
  ┌─ LLM 调用 2：事件摘要生成（见 §7.3） ───┐
  │ 输入：归档范围内各回合的 summary           │
  │      （若含 first_message 则一并纳入）     │
  │       + context                           │
  │ 输出：事件 title + 事件 summary            │
  └──────────────────────────────────────────┘
        │
        ▼
  创建 episode 记录
  更新归档范围内所有 rounds 的 episode_id
  若 first_message 参与了本次归档，标记 first_message_archived = true
        │
        ▼
  返回 { round_stored: true, episode_created: true, new_episode: {...} }
```

**方案 A 要点**：边界回合归入前一事件，下一事件从边界回合之后开始。数据上每个 round 严格归属一个 episode，不重叠。

---

## 6. 回滚机制

### 6.1 触发条件

在召回流程的同步检查阶段，若 `latest_round_id < DB 中 max(round_id)`，说明前端（SillyTavern）有楼层被删除，后端数据需要回滚。

### 6.2 回滚操作

设回滚点为 `R = latest_round_id`，执行以下操作（在单个事务中）：

1. **识别受影响的 episodes**：查找所有 `start_round_id > R` 或 `end_round_id > R` 的 episodes

2. **处理受影响的 episodes**：
   - 若 episode 的 `start_round_id > R`：整个 episode 在回滚范围内，直接删除
   - 若 episode 的 `start_round_id <= R` 且 `end_round_id > R`：episode 被部分截断，由于其摘要是基于完整范围生成的，已不可信 → **删除该 episode**，将其范围内 `round_id <= R` 的 rounds 的 episode_id 重置为 null

3. **删除回滚范围内的 rounds**：删除所有 `round_id > R` 的 rounds

4. **处理 first_message 状态**：若被删除的 episode 中包含 episode_id = 1（首个事件），则将 `first_message_archived` 重置为 false

### 6.3 回滚后状态

回滚完成后，被波及的 rounds 恢复为未归档状态，将在后续归档流程中重新参与事件边界检测和摘要生成。

---

## 7. LLM 提示词模板

以下为三个 LLM 调用点的提示词模板草案。实际使用时，`{{变量}}` 由系统填充。

### 7.1 召回：事件筛选

```
你是一个记忆管理助手。当前正在进行一段角色扮演对话，你需要判断哪些历史事件与当前对话相关。

## 当前上下文
{{recent_rounds_text}}
{{context.extra}}

## 用户最新输入
{{context.user_input}}

## 历史事件列表
{{#each episodes}}
- 事件{{episode_id}}：{{title}}
{{/each}}

## 任务
从上方的历史事件列表中，选出与当前对话上下文相关的事件。只选择确实有助于AI进行剧情演绎的事件，不要过度召回。

## 输出格式
仅输出一个JSON数组，包含所选事件的ID，例如：[2, 5, 7]
若无相关事件，输出空数组：[]
```

### 7.2 归档：事件边界检测

```
你是一个记忆管理助手。你需要判断以下一系列连续的对话回合中，最新的回合是否标志着一个事件的结束。

## 上下文
{{context.extra}}

## 待检测的回合摘要（按时间顺序）
{{#if include_first_message}}
[首条消息] {{first_message_summary}}
{{/if}}
{{#each unarchived_rounds}}
[回合{{round_id}}] {{summary}}
{{/each}}

## 判断标准
事件边界通常出现在：场景发生显著变化、时间出现明显跳跃、核心话题/冲突发生转折等情况下。
如果所有回合都在讲述同一个连贯的场景或事件，则不存在边界。

## 输出格式
仅输出一个JSON对象：
- 若不存在边界：{"has_boundary": false}
- 若存在边界：{"has_boundary": true, "boundary_round_id": <最后一个属于当前事件的回合ID>}
```

### 7.3 归档：事件摘要生成

```
你是一个记忆管理助手。请为以下一组对话回合生成一个事件摘要。

## 上下文
{{context.extra}}

## 事件包含的回合摘要
{{#if include_first_message}}
[首条消息] {{first_message_summary}}
{{/if}}
{{#each rounds_in_range}}
[回合{{round_id}}] {{summary}}
{{/each}}

## 任务
1. 为这组回合生成一个简短的事件标题（不超过20字）
2. 生成一段事件摘要，应包含关键情节、人物互动和情感变化，保留重要细节但去除冗余

## 输出格式
仅输出一个JSON对象：
{"title": "事件标题", "summary": "事件摘要内容"}
```

---

## 8. 扩展预留

以下设计点已为未来模块预留接口，当前不实现：

| 预留点 | 说明 |
|--------|------|
| enabled_modules | chats 表中的 JSON 数组，未来新增模块时只需扩展可选值（如 `"semantic"`, `"working"`, `"personality"`, `"lore"`） |
| /recall 响应结构 | 当前仅返回 `recalled_episodes`，未来可扩展 `semantic_memory`, `working_memory` 等字段 |
| /archive 响应结构 | 同上，可扩展其他模块的归档结果 |
| context 字段 | 召回和归档请求中的 context 为开放结构，仅承载后端不持有的外部信息；未来模块所需上下文可自由扩展 |
| 情节记忆预筛选 | 当事件数量增长后，可在 LLM 筛选前接入向量检索做粗筛，API 接口无需变更 |

---

## 9. 全局配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| recent_rounds_count | integer | 10 | 召回时后端从 rounds 表读取的最近回合数，用于组装 LLM 上下文 |
| llm_endpoint | string | — | 外部 LLM API 地址 |
| llm_model | string | — | 使用的模型标识 |

首期以全局配置文件或环境变量形式管理即可，未来可迁移为角色级配置。

---

## 10. 技术备忘

- 数据库：首期建议使用 SQLite，足够支撑单用户原型场景，后续可迁移
- LLM 调用：通过 HTTP 请求外部 LLM API，需要可配置的 endpoint 和 model 参数
- 事务性：回滚操作必须在单个数据库事务中完成，确保数据一致性
- 幂等性：归档接口应处理重复 round_id 的情况（相同 chat_id + round_id 重复提交时，跳过或更新）