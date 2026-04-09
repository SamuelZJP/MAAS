# 词条记忆模块（Lorebook）

## 1. 概述

词条记忆模块管理角色对话中的静态注入内容——角色设定、世界观背景、条件性描述等。本质上是 SillyTavern 世界书的简化版本，额外支持基于 Jinja2 的模板语法，可根据语义记忆变量动态渲染词条内容。

词条内容在初始化时从后端本地 YAML 文件载入数据库，运行时只读，不参与任何形式的归档。

---

## 2. 核心概念

| 概念 | 说明 |
|------|------|
| Entry（词条） | 一条可注入对话上下文的静态内容，可包含 Jinja2 模板语法 |
| 模板词条 | `has_template = true` 的词条，召回时需要语义记忆变量进行渲染 |
| 注入位置 | 词条插入对话上下文的方式：`character`（角色定义区）或 `depth`（按深度插入） |

---

## 3. 数据模型

### 3.1 lorebook_entries

| 字段 | 类型 | 说明 |
|------|------|------|
| chat_id | string, FK → chats | 所属角色 |
| entry_id | integer | 词条序号，同一 chat 内自增 |
| filename | string | 来源 YAML 文件名（不含扩展名），便于溯源 |
| content | text | 词条内容，可包含 Jinja2 模板语法 |
| position | string | 注入位置：`"character"` 或 `"depth"` |
| order | integer | 注入顺序（同 position 内排序） |
| depth | integer, nullable | 注入深度，仅 `position = "depth"` 时有效 |
| has_template | boolean | 是否包含模板语法 |
| enabled | boolean, default true | 是否启用 |
| created_at | datetime | 记录创建时间 |

主键：(chat_id, entry_id)

---

## 4. 文件存储结构

```
lorebook/
  苏菲/
    好感度反应.yaml
    服装描写.yaml
    世界观.yaml
  ...
```

每个 YAML 文件对应一条词条，文件内容即完整的词条定义：

```yaml
position: character
order: 10
depth: null
has_template: true
enabled: true
content: |
  {% if semantic_memory.苏菲.情感.好感度 > 20 %}
  苏菲有点喜欢上了<user>
  {% endif %}
```

YAML 文件是词条的 single source of truth，数据库为运行时缓存。

---

## 5. 初始化流程

在 `POST /chats` 中，若 `enabled_modules` 包含 `"lorebook"`：

```
检查 lorebook/{chat_id}/ 目录是否存在
若不存在 → 静默跳过，模块标记为启用但无词条数据
      │
      ▼
遍历目录下所有 .yaml 文件
      │
      ▼
按文件名排序后逐文件解析，校验必填字段（position, order, content）
      │
      ▼
按文件顺序分配 entry_id（从 1 起递增）
      │
      ▼
写入 lorebook_entries 表
```

补充约束：

- `lorebook` 模块只能在 `POST /chats` 初始化时决定，初始化后不允许通过 `PATCH /chats/{chat_id}` 新增或移除
- 初始化后默认 YAML 不再修改，不提供热更新或重载机制
- 若目录存在但某个 YAML 文件非法，则整个 `POST /chats` 失败并返回 400

删除 chat（`DELETE /chats/{chat_id}`）时级联删除该 chat 下所有 lorebook_entries 记录。

---

## 6. 召回流程

词条记忆模块在 `POST /recall` 的编排流程中被调用，返回全量词条。

```
检查 lorebook 模块是否启用
若未启用 → 跳过
      │
      ▼
从 lorebook_entries 表读取该 chat 下所有 enabled = true 的词条
      │
      ▼
检查 semantic 模块是否启用
      │
      ├─ 未启用 → 过滤掉所有 has_template = true 的词条
      │
      └─ 已启用 → pipeline 传入 semantic_memory（由编排层提供，非模块直接耦合）
                  对 has_template = true 的词条执行 Jinja2 渲染
                  渲染上下文：{ "semantic_memory": <最新语义记忆快照> }
                  若单条渲染失败 → 跳过该条，记录日志
      │
      ▼
返回 lorebook_entries 列表
每条包含：entry_id, content（已渲染）, position, order, depth
```

### 6.1 模块间依赖（编排层处理）

recall_pipeline 中的调用顺序：

1. semantic recall → 获取 semantic_memory
2. lorebook recall（semantic_memory 作为参数传入）
3. episodic recall（与 lorebook 无依赖）

### 6.2 排序与过滤规则

- 后端按 `(position, depth, order, entry_id)` 排序返回
- `position` 的固定优先级为：`character` 在前，`depth` 在后
- 对于 `has_template = false` 的词条，若 `content.strip()` 为空字符串，则不返回
- 对于模板词条，若渲染结果去首尾空白后为空字符串，则不返回

lorebook 模块本身不引用 semantic 模块的任何代码，仅接收编排层传入的数据。

---

## 7. 归档流程

本模块不参与归档。`POST /archive` 中直接跳过。

---

## 8. 回滚对接

本模块存储静态内容，不随回合变化，无需回滚处理。

---

## 9. 模板语法

使用 Jinja2 引擎，渲染上下文为完整的语义记忆快照对象。

### 9.1 可用变量

模板中通过 `semantic_memory` 访问语义记忆的全部字段，路径与 Schema 定义一致：

- `semantic_memory.世界.时间`
- `semantic_memory.苏菲.情感.好感度`
- `semantic_memory.苏菲.服装.外套`

### 9.2 支持的语法

标准 Jinja2 语法子集：

- 条件：`{% if %}` / `{% elif %}` / `{% else %}` / `{% endif %}`
- 变量输出：`{{ semantic_memory.苏菲.姿势 }}`
- 循环、宏等高级语法不做限制，但预期主要使用条件判断

未定义变量按错误处理；该词条会被跳过并记录日志，不会回退为默认空字符串。

### 9.3 示例

```jinja2
{% if semantic_memory.苏菲.情感.好感度 >= 80 %}
苏菲对<user>非常亲近，会主动寻求肢体接触。
{% elif semantic_memory.苏菲.情感.好感度 >= 40 %}
苏菲对<user>有好感，态度友善。
{% else %}
苏菲对<user>保持礼貌但有距离感。
{% endif %}
```

---

## 10. 响应结构

`POST /recall` 响应中新增 `lorebook_entries` 字段：

```json
{
  "recalled_episodes": [...],
  "semantic_memory": {...},
  "lorebook_entries": [
    {
      "entry_id": 1,
      "content": "苏菲对<user>非常亲近，会主动寻求肢体接触。",
      "position": "character",
      "order": 10,
      "depth": null
    },
    {
      "entry_id": 2,
      "content": "当前世界处于魔法纪元...",
      "position": "depth",
      "order": 1,
      "depth": 4
    }
  ],
  "rollback_performed": false,
  "rollback_to_round_id": null
}
```

若模块未启用或无词条，`lorebook_entries` 为空数组。

---

## 11. 目录结构扩展

```
modules/
  lorebook/
    __init__.py
    recall.py           # 召回逻辑（读取词条 + 模板渲染）
    loader.py           # 从 YAML 文件加载词条到数据库

lorebook/               # 角色词条文件（YAML）
  苏菲/
    好感度反应.yaml
    服装描写.yaml
    ...

repository/crud/
  lorebook.py           # lorebook_entries 表的读写操作
```

---

## 12. 校验规则

- `position` 仅允许 `character` 或 `depth`
- `position = "depth"` 时，`depth` 必填且必须为非负整数
- `position = "character"` 时，`depth` 必须为 `null`
- `order` 必须为非负整数
- `content` 必须是字符串；空字符串允许存储，但召回时不返回
- 允许多条词条拥有完全相同的 `position`、`depth`、`order`
