# FastAPI 应用入口，负责生命周期管理和中间件配置

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from repository.database import create_all_tables, dispose_engine


# 应用生命周期：启动时建表，关闭时释放数据库连接
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await create_all_tables()
    yield
    await dispose_engine()

app = FastAPI(title="MAAS", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


# 健康检查端点
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
