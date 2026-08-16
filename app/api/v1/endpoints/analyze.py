from fastapi import APIRouter
from app.schemas.risk import RiskAnalysisRequest, RiskAnalysisResponse
from app.services.risk_analyzer import risk_analyzer_service

router = APIRouter()


@router.post("/analyze", response_model=RiskAnalysisResponse)
async def analyze_situation(request: RiskAnalysisRequest) -> RiskAnalysisResponse:
    """Analyze a business situation and return structured risk assessment."""
    return risk_analyzer_service.analyze_situation(request)
