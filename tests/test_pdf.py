from fastapi.testclient import TestClient
from app.main import app
from app.schemas.risk import RiskAnalysisRequest
from app.services.risk_analyzer import risk_analyzer_service
from app.services.pdf_service import pdf_generator_service


def test_pdf_generation():
    """Should generate a PDF (or text fallback) from analysis results."""
    req = RiskAnalysisRequest(situation="Supplier delays have disrupted our delivery timelines.")
    analysis = risk_analyzer_service.analyze_situation(req)
    pdf_bytes = pdf_generator_service.generate_pdf_report(analysis)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100


def test_pdf_endpoint_refuses_a_report_that_failed_final_qc():
    analysis = risk_analyzer_service.analyze_situation(RiskAnalysisRequest(situation="Revenue fell 30%."))
    analysis.report_validation.valid_for_distribution = False
    analysis.report_validation.status = "REANALYSIS_REQUIRED"

    response = TestClient(app).post("/api/v1/reports/pdf", json=analysis.model_dump(mode="json"))
    assert response.status_code == 422
    assert "failed final QC" in response.json()["detail"]
