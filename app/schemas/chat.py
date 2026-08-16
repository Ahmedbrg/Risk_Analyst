from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.risk import RiskAnalysisResponse


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    risk_analysis: Optional[RiskAnalysisResponse] = None


class ConversationSession(BaseModel):
    """Tracks the full conversation history."""
    conversation_id: str
    title: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    messages: List[ChatMessage] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """What the user sends in the chat."""
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1)
    use_crew_ai: bool = False
    include_rag: bool = False
