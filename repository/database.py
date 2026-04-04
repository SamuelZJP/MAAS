# 数据库引擎初始化、会话工厂和生命周期管理

from collections.abc import AsyncIterator
import os

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from repository.models import Base


DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./maas.db"
DATABASE_URL = os.getenv("MAAS_DATABASE_URL", DEFAULT_DATABASE_URL)

engine: AsyncEngine = create_async_engine(DATABASE_URL, future=True)


# SQLite 连接时启用外键约束
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    if "sqlite" not in DATABASE_URL:
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# FastAPI 依赖注入：获取异步数据库会话
async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        yield session


# 根据 ORM 模型定义创建所有数据库表
async def create_all_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


# 释放数据库引擎连接池
async def dispose_engine() -> None:
    await engine.dispose()


__all__ = [
    "AsyncSessionFactory",
    "DATABASE_URL",
    "create_all_tables",
    "dispose_engine",
    "engine",
    "get_session",
]
