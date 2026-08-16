import uuid
from typing import Dict, Optional
from datetime import datetime, timezone

from app.schemas.chat import ConversationSession, ChatMessage


class ConversationMemoryManager:
    """
    Keeps conversation history in memory.

    I used a simple dictionary instead of a database for the MVP.
    The sliding window (max 10 messages) prevents sending too much
    context to the LLM which would waste tokens and money.

    TODO: Move to PostgreSQL in Phase 11.
    """

    def __init__(self, max_context_messages: int = 10):
        self._sessions: Dict[str, ConversationSession] = {}
        self.max_context_messages = max_context_messages

    def get_or_create_session(self, conversation_id: Optional[str] = None) -> ConversationSession:
        """Get existing session or create a new one."""
        if conversation_id and conversation_id in self._sessions:
            return self._sessions[conversation_id]

        new_id = conversation_id or str(uuid.uuid4())
        session = ConversationSession(
            conversation_id=new_id,
            title="New Risk Analysis",
            created_at=datetime.now(timezone.utc).isoformat(),
            messages=[],
        )
        self._sessions[new_id] = session
        return session

    def add_message(self, conversation_id: str, message: ChatMessage) -> ConversationSession:
        """Add a message to the conversation."""
        session = self.get_or_create_session(conversation_id)
        session.messages.append(message)
        session.updated_at = datetime.now(timezone.utc).isoformat()

        # Set title from first user message
        if len(session.messages) == 1 and message.role == "user":
            snippet = message.content[:40].replace("\n", " ").strip()
            session.title = f"Risk Analysis: {snippet}..."

        return session

    def get_context_prompt(self, conversation_id: str) -> str:
        """
        Build a context string from recent messages for the LLM.
        Only takes the last N messages to stay within token limits.
        """
        session = self.get_or_create_session(conversation_id)
        if not session.messages:
            return ""

        recent = session.messages[-self.max_context_messages:]
        lines = []
        for msg in recent:
            label = "USER" if msg.role == "user" else "AI RISK ANALYST"
            lines.append(f"{label}: {msg.content}")

        return "\n--- Previous conversation ---\n" + "\n".join(lines) + "\n---\n"


# Single instance shared across the app
memory_manager = ConversationMemoryManager()
