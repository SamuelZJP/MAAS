from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.router import api_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="MAAS", lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")
