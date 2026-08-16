import httpx
from fastapi import APIRouter, HTTPException, Response
from app.schemas.risk import RiskAnalysisResponse
from app.core.quality import RiskReportQualityGate
from app.core.fact_validation import FactValidator
from app.services.pdf_service import pdf_generator_service
from app.config import settings

router = APIRouter()


def _require_distributable_report(analysis: RiskAnalysisResponse) -> None:
    """Recompute critical QC checks; never trust a client-supplied VALID flag."""
    important_fact_ids = FactValidator.validate(analysis.extracted_facts).important_fact_ids
    qc = RiskReportQualityGate.output_warnings(
        analysis.identified_risks, analysis.priority_actions, analysis.extracted_facts, important_fact_ids
    )
    validation = analysis.report_validation
    if (
        not validation
        or validation.status != "VALID"
        or not validation.valid_for_distribution
        or qc["warnings"]
    ):
        raise HTTPException(
            status_code=422,
            detail="Report failed final QC and is not valid for distribution. Re-analysis is required.",
        )


@router.post("/reports/pdf")
async def generate_pdf_report(analysis: RiskAnalysisResponse):
    """Generate and download a PDF risk report."""
    _require_distributable_report(analysis)
    pdf_bytes = pdf_generator_service.generate_pdf_report(analysis)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Risk_Report_{analysis.analysis_id[:8]}.pdf"
        },
    )


@router.post("/reports/n8n-trigger")
async def trigger_n8n_workflow(analysis: RiskAnalysisResponse, recipient_email: str):
    """
    Send analysis results to n8n webhook for automated email delivery.
    If n8n is not running, the payload is logged instead.
    """
    _require_distributable_report(analysis)

    payload = {
        "analysis_id": analysis.analysis_id,
        "recipient_email": recipient_email,
        "overall_risk": analysis.overall_risk.value,
        "executive_summary": analysis.executive_summary,
        "high_risk_count": sum(
            1 for r in analysis.identified_risks
            if r.severity.value in ["HIGH", "CRITICAL"]
        ),
        "priority_actions": [p.action for p in analysis.priority_actions],
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(settings.N8N_WEBHOOK_URL, json=payload)
            return {"status": "sent", "n8n_status_code": resp.status_code, "payload": payload}
    except Exception as e:
        # n8n is probably not running - that's fine for development
        return {"status": "n8n_offline", "message": str(e), "payload": payload}
