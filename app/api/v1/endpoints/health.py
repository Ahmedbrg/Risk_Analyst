from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    environment: str
    app_name: str
    version: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def check_health() -> HealthResponse:
    """Check if the API server is running."""
    return HealthResponse(
        status="ok",
        environment=settings.APP_ENV,
        app_name=settings.APP_NAME,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
