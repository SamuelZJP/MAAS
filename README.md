# MAAS

MAAS 是一个面向角色对话场景的记忆后端原型，基于 FastAPI、SQLite 和异步 SQLAlchemy 实现，围绕“召回”和“归档”两条主流程编排情节记忆、语义记忆与词条记忆模块。

当前接口基础路径为 `/api/v1`，项目首期定位为单用户原型，默认使用本地 SQLite 数据库。

## 项目简介

- 对话以 `Chat` 为单位管理，`chat_id` 当前约定为角色名。
- 系统以 `Round` 作为最小记录单位，每轮包含用户输入、AI 回复和后端生成的摘要。
- 记忆模块当前支持 `episodic`、`semantic`、`lorebook`，并通过 `enabled_modules` 控制启用状态。
- `POST /recall` 用于 AI 生成前的记忆召回，`POST /archive` 用于 AI 回复后的记忆归档。

## 环境要求与安装

- Python `3.11+`
- SQLite（默认通过 `aiosqlite` 使用本地文件数据库）

安装步骤：

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

## 配置说明

项目通过环境变量或 `.env` 文件加载配置，统一使用 `MAAS_` 前缀。

常用配置项：

- `MAAS_DATABASE_URL`：数据库连接串，默认值为 `sqlite+aiosqlite:///./maas.db`
- `MAAS_RECENT_ROUNDS_COUNT`：召回时读取的近期回合数，默认 `10`
- `MAAS_LLM_ENDPOINT`：外部 LLM API 地址
- `MAAS_LLM_MODEL`：外部 LLM 模型标识
- `MAAS_LLM_API_KEY`：外部 LLM API Key
- `MAAS_LLM_TIMEOUT_SECONDS`：LLM 请求超时时间，默认 `30.0`
- `MAAS_LLM_MAX_RETRIES`：LLM 请求最大重试次数，默认 `2`
- `MAAS_LLM_MOCK_MODE`：是否启用内置 mock 响应，默认 `false`

示例 `.env`：

```env
MAAS_DATABASE_URL=sqlite+aiosqlite:///./maas.db
MAAS_LLM_ENDPOINT=https://api.deepseek.com/chat/completions
MAAS_LLM_MODEL=deepseek-chat
MAAS_LLM_API_KEY=[TODO]
MAAS_LLM_TIMEOUT_SECONDS=30
MAAS_LLM_MAX_RETRIES=2
MAAS_LLM_MOCK_MODE=false
MAAS_RECENT_ROUNDS_COUNT=10
```

补充说明：

- 启用 `semantic` 时，需要存在 `data/{chat_id}.py`
- 启用 `lorebook` 时，需要存在 `lorebook/{chat_id}/` 下的合法 YAML 词条文件

## 启动方式

开发环境可直接使用 Uvicorn 启动：

```bash
uvicorn main:app --reload
```

服务启动后会自动按 ORM 定义创建数据库表，并默认提供健康检查接口：

- `GET /health`

## 快速上手

1. 安装依赖并准备 `.env`
2. 按需准备角色语义 Schema：`data/{chat_id}.py`
3. 按需准备角色词条目录：`lorebook/{chat_id}/`
4. 启动服务：`uvicorn main:app --reload`
5. 调用 `POST /api/v1/chats` 初始化角色对话
6. 在对话流程中调用 `POST /api/v1/recall` 和 `POST /api/v1/archive`

初始化角色对话示例：

```json
{
  "chat_id": "苏菲",
  "first_message": "你好，我是苏菲。",
  "enabled_modules": ["episodic", "semantic", "lorebook"]
}
```

最小对接流程：

- 先调用 `POST /api/v1/chats` 创建 chat
- 用户输入后调用 `POST /api/v1/recall`
- AI 回复后调用 `POST /api/v1/archive`
- 调试或排查时，可使用 `/api/v1/chats/{chat_id}/rounds`、`/episodes`、`/semantic` 相关管理接口

## 模块说明

- `api`：HTTP 接口层，负责参数校验、路由组织和请求转发。
- `schemas`：定义请求体、响应体与接口使用的 Pydantic 模型。
- `core`：编排召回、归档和回滚同步等主流程。
- `modules/episodic`：处理情节记忆的召回、边界检测与事件归档。
- `modules/semantic`：处理语义记忆快照的读取、更新、校验与加载。
- `modules/lorebook`：负责词条加载、模板渲染和词条召回。
- `modules/working`：为未来工作记忆模块预留的目录。
- `repository`：封装数据库引擎、ORM 模型和 CRUD 访问逻辑。
- `shared`：提供 LLM 调用、摘要生成和提示词渲染等通用能力。
- `data`：存放角色级语义记忆 Schema。
- `lorebook`：存放角色级词条 YAML，作为词条内容来源。
- `docs`：项目文档。

## API 文档入口

- Swagger UI：`/docs`
- ReDoc：`/redoc`
- 路由前缀：`/api/v1`

## 说明

- 生产部署方式：[TODO]
- 测试方式：[TODO]
- 示例角色资源规范补充：[TODO]
