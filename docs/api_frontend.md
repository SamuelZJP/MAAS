# MAAS 前端 API 文档

基础路径：`/api/v1`

模块枚举：`episodic`、`semantic`、`lorebook`

## 1. 初始化角色对话

`POST /chats`

请求示例：

```json
{
  "chat_id": "苏菲",
  "first_message": "你好，我是苏菲。",
  "enabled_modules": ["episodic", "semantic", "lorebook"]
}
```

返回示例：

```json
{
  "chat_id": "苏菲",
  "first_message": "你好，我是苏菲。",
  "first_message_archived": false,
  "enabled_modules": ["episodic", "semantic", "lorebook"],
  "created_at": "2026-04-09T10:00:00Z"
}
```

说明：

- 当前正式约定 `chat_id == 角色名`
- `semantic` 和 `lorebook` 只能在初始化时确定
- 若启用了 `semantic` 但缺少对应 `data/{chat_id}.py`，返回 `400`
- 若启用了 `lorebook` 且词条 YAML 非法，返回 `400`

## 2. 获取角色对话配置

`GET /chats/{chat_id}`

返回示例：

```json
{
  "chat_id": "苏菲",
  "first_message": "你好，我是苏菲。",
  "first_message_archived": false,
  "enabled_modules": ["episodic", "semantic", "lorebook"],
  "created_at": "2026-04-09T10:00:00Z"
}
```

## 3. 删除角色对话

`DELETE /chats/{chat_id}`

返回：

```http
204 No Content
```

## 4. 记忆召回

`POST /recall`

调用时机：用户输入后，AI 生成前。

请求示例：

```json
{
  "chat_id": "苏菲",
  "latest_round_id": 15,
  "recall_start_round_id": 3,
  "recall_end_round_id": 8,
  "context": {
    "user_input": "你还记得我们之前在教室里的事吗？",
    "extra": {
      "speaker": "user"
    }
  }
}
```

返回示例：

```json
{
  "recalled_episodes": [
    {
      "episode_id": 3,
      "title": "教室里的误会",
      "summary": "苏菲在教室中误解了用户的意图，随后两人解释清楚。"
    }
  ],
  "semantic_memory": {
    "世界": {
      "日期": "2026-04-08 星期三",
      "时间": "14:30",
      "地点": "教室"
    },
    "苏菲": {
      "情感": {
        "好感度": 45,
        "爱意值": 0,
        "当前关系": "师生"
      }
    }
  },
  "lorebook_entries": [
    {
      "entry_id": 1,
      "content": "苏菲对<user>有好感，态度友善。",
      "position": "character",
      "order": 10,
      "depth": null
    },
    {
      "entry_id": 2,
      "content": "当前世界处于魔法纪元。",
      "position": "depth",
      "order": 1,
      "depth": 4
    }
  ],
  "rollback_performed": false,
  "rollback_to_round_id": null
}
```

说明：

- `latest_round_id` 是本次用户输入之前的最新楼层号；首次对话传 `0`
- 只有同时传入 `recall_start_round_id` 和 `recall_end_round_id` 时，才会执行情节记忆召回
- `semantic_memory` 在未启用语义模块时为 `null`
- `lorebook_entries` 在未启用词条模块或无可用词条时为空数组
- 若检测到前端删楼并触发回滚，`rollback_performed` 为 `true`

## 5. 记忆归档

`POST /archive`

调用时机：AI 回复后。

请求示例：

```json
{
  "chat_id": "苏菲",
  "round_id": 16,
  "user_input": "你还记得我们之前在教室里的事吗？",
  "ai_response": "我当然记得，那天你突然靠近我，把我吓了一跳。",
  "summary": "兼容保留字段，后端忽略该值并自行生成摘要。",
  "context": {
    "extra": {
      "speaker": "assistant"
    }
  }
}
```

返回示例：

```json
{
  "round_stored": true,
  "episode_created": true,
  "new_episode": {
    "episode_id": 5,
    "title": "重提教室误会",
    "summary": "用户重新提起教室中的误会，苏菲给出明确回应，两人围绕旧事继续交流。",
    "chat_id": "苏菲",
    "start_round_id": 12,
    "end_round_id": 16,
    "created_at": "2026-04-09T10:05:00Z"
  },
  "semantic_updated": true,
  "semantic_memory": {
    "世界": {
      "日期": "2026-04-08 星期三",
      "时间": "15:00",
      "地点": "教室"
    },
    "苏菲": {
      "情感": {
        "好感度": 50,
        "爱意值": 0,
        "当前关系": "师生"
      }
    }
  }
}
```

说明：

- `round_id` 由前端递增维护
- `summary` 当前为兼容保留字段，后端不会使用前端传入内容
- 后端会调用外部 LLM 生成回合摘要；若启用了语义模块，会将当前语义记忆中的日期、时间、地点注入摘要提示词
- 若同一个 `chat_id + round_id` 被重复提交，返回中 `round_stored` 为 `false`
- `episode_created` 表示本轮是否产生了新的事件归档
- `semantic_updated` 表示本轮语义记忆是否发生变化

## 获得某一回合的状态变量

`GET /api/v1/chats/{chat_id}/semantic/{round_id}`

返回示例:
```json
{
    "chat_id": "string",
    "round_id": 0,
    "content": {
        "property1": "string",
        "property2": "string"
    },
    "created_at": "2019-08-24T14:15:22.123Z"
}
```

## 6. 常见错误

返回格式：

```json
{
  "detail": "错误信息"
}
```

常见状态码：

- `400 Bad Request`：请求参数非法，或初始化时语义 Schema / lorebook YAML 有问题
- `404 Not Found`：`chat_id` 不存在
