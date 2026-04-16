# 情节记忆模块（Episodic Memory）

## 1. 概述

情节记忆模块负责将连续的对话回合压缩为"事件"（Episode），并在后续对话中召回相关事件，为 AI 提供长期剧情记忆能力。

本模块是 MAAS 首期实现的核心功能模块。

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| Episode（事件） | 一到多个连续对话回合的压缩产物，是记忆召回时的基本单位 |
| 事件边界 | 相邻回合之间剧情发生显著转折的位置 |

---

## 3. 数据模型

### 3.1 episodes

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

### 3.2 与 rounds 的关系

- `rounds.episode_id` 引用同 chat 下 `episodes.episode_id`
- 一个 episode 覆盖 `[start_round_id, end_round_id]` 范围内的所有 rounds
- 每个 round 最多归属一个 episode（`episode_id` 为标量），不重叠

---

## 4. CRUD API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /chats/{chat_id}/episodes | 获取该角色所有事件 |
| GET | /chats/{chat_id}/episodes/{episode_id} | 获取单个事件详情 |
| DELETE | /chats/{chat_id}/episodes/{episode_id} | 删除单个事件（其下 rounds 的 episode_id 重置为 null） |

---

## 5. 召回流程

情节记忆模块在 `POST /recall` 的编排流程中被调用，负责筛选与当前对话相关的历史事件。

```
检查 episodic 模块是否启用
若未启用 → 跳过
      │
      ▼
若请求未同时携带 recall_start_round_id 和 recall_end_round_id：
  → 跳过召回，返回空结果
      │
      ▼
查询与 [start, end] 区间有重叠的 episodes
→ 提取 (episode_id, title) 列表
若列表为空 → 返回空结果
      │
      ▼
从 rounds 表读取最近 N 轮摘要（N = recent_rounds_count 全局配置）
      │
      ▼
组装 LLM 请求（见 §7.1 召回提示词）
输入：事件列表 + 近期回合摘要 + context（user_input, extra）
输出：LLM 返回所需的 episode_id 列表
      │
      ▼
根据返回的 episode_id 查询对应 episodes 的完整摘要
      │
      ▼
返回 recalled_episodes
```

---

## 6. 归档流程

情节记忆模块在 `POST /archive` 的编排流程中被调用，负责检测事件边界并生成事件摘要。

```
检查 episodic 模块是否启用
若未启用 → 跳过
      │
      ▼
收集待处理内容：
  - 所有 episode_id 为 null 的 rounds（按 round_id 升序），提取其 summary
  - 若 first_message_archived 为 false，将 first_message 也纳入（置于最前）
      │
      ▼
┌─ LLM 调用 1：事件边界检测（见 §7.2） ───┐
│ 输入：已归档最后一个回合的全量对话+摘要     │
│      + 待处理回合的摘要列表                │
│      + 未归档最后一个回合的全量对话+摘要   │
│      + context                            │
│ 输出：最新回合是否使当前事件闭合(boolean)  │
└──────────────────────────────────────────┘
      │
 无边界 → 返回 { episode_created: false }
      │
 有边界 ↓
      ▼
确定归档范围：当前所有未归档回合
      │
      ▼
┌─ LLM 调用 2：事件摘要生成（见 §7.3） ───┐
│ 输入：已归档最后一个回合的全量对话+摘要     │
│      + 归档范围内各回合的全量对话+摘要     │
│      （若含 first_message 则一并纳入）     │
│      + context                            │
│ 输出：事件 title + 事件 summary            │
└──────────────────────────────────────────┘
      │
      ▼
创建 episode 记录
更新归档范围内所有 rounds 的 episode_id
若 first_message 参与了本次归档，标记 first_message_archived = true
      │
      ▼
返回 { episode_created: true, new_episode: {...} }
```

**归档要点**：系统只判断最新回合是否使当前事件闭合；一旦闭合，当前所有未归档回合整体归档为一个 episode。为避免边界回合中的跨事件信息造成摘要错位，边界检测和摘要生成都会额外引入“已归档的最后一个回合”作为桥接上下文，但它不参与本次 episode 的实际归档范围。数据上每个 round 仍严格归属一个 episode，不重叠。

---

## 7. LLM 提示词模板

以下为本模块三个 LLM 调用点的提示词模板。实际使用时，`{{变量}}` 由系统填充。

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

注意：若系统已对历史事件做了回合范围预筛选，则你只需在给定候选事件中继续判断相关性，无需补选范围外事件。

## 输出格式
仅输出一个JSON数组，包含所选事件的ID，例如：[2, 5, 7]
若无相关事件，输出空数组：[]
```

### 7.2 归档：事件边界检测

```
你是一个记忆管理助手。你需要判断以下一系列连续的对话回合中，最新的回合是否标志着当前事件的结束。

## 上下文
{{context.extra}}

## 已归档的最后一个对话回合（跨事件边界的桥接上下文）
{{archived_last_round_full_text_and_summary}}

## 待检测的回合摘要（按时间顺序）
{{#if include_first_message}}
[首条消息] {{first_message_summary}}
{{/if}}
{{#each unarchived_rounds}}
[回合{{round_id}}] {{summary}}
{{/each}}

## 未归档的最后一个对话回合（完整内容）
{{latest_unarchived_round_full_text_and_summary}}

## 判断标准
事件边界通常出现在：场景发生显著变化、时间出现明显跳跃、核心话题/冲突发生转折等情况下。
如果所有回合都在讲述同一个连贯的场景或事件，则不存在边界。
注意：“已归档的最后一个对话回合”位于上一事件末尾，但其中已经出现当前事件的开头信息。判断时应忽略其中属于上一事件的内容，只把属于当前事件的部分当作参考。

## 输出格式
仅输出一个JSON对象：
- 若不存在边界：{"has_boundary": false}
- 若存在边界：{"has_boundary": true}
```

### 7.3 归档：事件摘要生成

```
你是一个记忆管理助手。请为以下一组对话回合生成一个事件摘要。

## 上下文
{{context.extra}}

## 已归档的最后一个对话回合（跨事件边界的桥接上下文）
{{archived_last_round_full_text_and_summary}}

## 事件包含的回合
{{#if include_first_message}}
[首条消息] {{first_message_summary}}
{{/if}}
{{#each rounds_in_range}}
[回合{{round_id}}] {{full_text_and_summary}}
{{/each}}

## 任务
1. 为这组回合生成一个简短的事件标题（不超过20字）
2. 生成一段事件摘要，应包含关键情节、人物互动和情感变化，保留重要细节但去除冗余
3. “已归档的最后一个对话回合”中可能包含当前事件的开头信息，但要忽略其中属于上一事件的部分
4. 最后一个对话回合中可能已经出现下一事件的开头信息，生成当前事件摘要时要忽略那部分内容

## 输出格式
仅输出一个JSON对象：
{"title": "事件标题", "summary": "事件摘要内容"}
```
