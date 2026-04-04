MAAS/
│
├── main.py                            # FastAPI 应用入口，lifespan 管理
├── config.py                          # 全局配置（pydantic-settings）
│
├── api/                               # HTTP 接口层，只做参数校验和转发
│   ├── __init__.py
│   ├── router.py                      # 聚合所有路由
│   ├── chats.py                       # POST/GET/PATCH/DELETE /chats
│   ├── recall.py                      # POST /recall
│   ├── archive.py                     # POST /archive
│   └── admin.py                       # 管理/调试端点（rounds、episodes CRUD）
│
├── schemas/                           # Pydantic 模型（请求体/响应体）
│   ├── __init__.py                    # api 和 core 都会引用，因此独立
│   ├── chats.py
│   ├── recall.py
│   ├── archive.py
│   └── episodes.py
│
├── core/                              # 编排层：管理流程和模块间依赖
│   ├── __init__.py
│   ├── recall_pipeline.py            # 召回主流程编排
│   ├── archive_pipeline.py           # 归档主流程编排
│   └── sync.py                        # 回滚/同步逻辑
│
├── modules/                           # 各功能模块，结构统一
│   ├── __init__.py
│   ├── episodic/                      # 情节记忆（本期实现）
│   │   ├── __init__.py
│   │   ├── recall.py                  # 情节记忆的召回逻辑
│   │   ├── archive.py                 # 情节记忆的归档逻辑（边界检测+事件生成）
│   │   └── prompts.py                 # 情节记忆专用提示词模板
│   ├── semantic/                      # 语义记忆（未来）
│   │   └── __init__.py
│   ├── working/                       # 工作记忆（未来）
│   │   └── __init__.py
│   ├── personality/                   # 人格系统（未来）
│   │   └── __init__.py
│   └── lore/                          # 背景信息（未来）
│       └── __init__.py
│
├── repository/                        # 数据访问层
│   ├── __init__.py
│   ├── database.py                    # 引擎初始化、会话工厂
│   ├── models.py                      # SQLAlchemy ORM 模型定义
│   └── crud/                          # 按表拆分的 CRUD 操作
│       ├── __init__.py
│       ├── chats.py
│       ├── rounds.py
│       └── episodes.py
│
└── shared/                            # 跨模块通用工具
    ├── __init__.py
    ├── llm_client.py                  # LLM 统一调用封装
    ├── summarizer.py                  # 通用摘要生成（事件归档、未来的回合摘要等复用）
    └── prompt_utils.py                # 提示词模板渲染工具