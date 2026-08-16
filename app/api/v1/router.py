from fastapi import APIRouter

from app.api.v1.endpoints import health, analyze, chat, documents, reports

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(analyze.router, tags=["Risk Analysis"])
api_router.include_router(chat.router, tags=["Chat"])
api_router.include_router(documents.router, tags=["Documents"])
api_router.include_router(reports.router, tags=["Reports"])
