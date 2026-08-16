from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatMessage, ConversationSession
from app.schemas.risk import RiskAnalysisRequest
from app.core.memory import memory_manager
from app.services.risk_analyzer import risk_analyzer_service

router = APIRouter()


@router.post("/chat", response_model=ChatMessage)
async def chat_with_analyst(request: ChatRequest) -> ChatMessage:
    """
    Send a message and get a risk analysis response.
    Maintains conversation context for multi-turn dialogue.
    """
    session = memory_manager.get_or_create_session(request.conversation_id)

    # Save user message
    user_msg = ChatMessage(role="user", content=request.message)
    memory_manager.add_message(session.conversation_id, user_msg)

    # Check for simple conversational greetings or help requests
    clean_msg = request.message.strip().lower().rstrip("!?.")
    greetings = {
        "hi", "hello", "hey", "hola", "bonjour", "help", "who are you", 
        "what can you do", "good morning", "good evening", "hi there", "hello there", "start", "test"
    }

    if clean_msg in greetings:
        response_text = (
            "Hello! I am your AI Risk Analyst.\n\n"
            "I can evaluate complex business, financial, supplier, legal, and operational situations. "
            "Please describe your scenario in natural language, for example:\n\n"
            "> 'Our revenue decreased 30% during the last six months. Two major suppliers are frequently late, "
            "one important contract expires next month, and we have limited cash reserves. Analyze the risks.'\n\n"
            "You can also upload documents (PDF, DOCX, TXT) or toggle CrewAI multi-agent mode!"
        )
        assistant_msg = ChatMessage(
            role="assistant",
            content=response_text,
            risk_analysis=None,
        )
        memory_manager.add_message(session.conversation_id, assistant_msg)
        return assistant_msg

    # Run full risk analysis
    analysis_req = RiskAnalysisRequest(
        situation=request.message,
        conversation_id=session.conversation_id,
        use_crew_ai=request.use_crew_ai,
        include_rag=request.include_rag,
    )
    analysis_result = risk_analyzer_service.analyze_situation(analysis_req)

    # Build response text summary
    response_text = (
        f"### Risk Assessment Complete\n\n"
        f"**Overall Risk Severity:** `{analysis_result.overall_risk.value}` (Score: {analysis_result.overall_score:.1f}/5.0)\n\n"
        f"{analysis_result.executive_summary}\n\n"
        f"Identified **{len(analysis_result.identified_risks)}** risk vectors with **{len(analysis_result.priority_actions)}** priority mitigation actions."
    )

    assistant_msg = ChatMessage(
        role="assistant",
        content=response_text,
        risk_analysis=analysis_result,
    )
    memory_manager.add_message(session.conversation_id, assistant_msg)

    return assistant_msg


@router.get("/conversations/{conversation_id}", response_model=ConversationSession)
async def get_conversation(conversation_id: str) -> ConversationSession:
    """Get the full conversation history."""
    return memory_manager.get_or_create_session(conversation_id)
