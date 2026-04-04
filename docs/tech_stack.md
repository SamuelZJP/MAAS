**核心组合**：Python 3.11+ / FastAPI / SQLite（aiosqlite）

- **FastAPI**：原生 async、自动生成 OpenAPI 文档方便前端对接和调试，轻量但不简陋
- **SQLite + aiosqlite**：首期零部署成本，通过 SQLAlchemy（async 模式）做 ORM 的话，后续迁移到 PostgreSQL 只需换连接串
- **LLM 对接**：Python 是所有主流 LLM SDK（OpenAI、Anthropic、各类兼容接口）的一等公民，httpx 做通用 HTTP 调用也很顺手
