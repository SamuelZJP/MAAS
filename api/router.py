from fastapi import APIRouter

from api import admin, archive, chats, recall

api_router = APIRouter()
api_router.include_router(chats.router, tags=["chats"])
api_router.include_router(recall.router, tags=["recall"])
api_router.include_router(archive.router, tags=["archive"])
api_router.include_router(admin.router, tags=["admin"])
