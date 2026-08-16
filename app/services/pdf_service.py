"""
AI Risk Analyst — Production-Grade Executive PDF Report Generation Engine.
"""

from io import BytesIO
from datetime import datetime, timezone
from app.schemas.risk import RiskAnalysisResponse


class PDFReportGeneratorService:
    """
    ReportLab PDF Generation Engine.
    Produces high-fidelity, boardroom-ready Risk Assessment briefings
    with clean table cell wrapping, traceable citations, and audit metadata.
    """

    def generate_pdf_report(self, analysis: RiskAnalysisResponse) -> bytes:
        buffer = BytesIO()

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
            )

            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                leftMargin=36,
                rightMargin=36,
                topMargin=36,
                bottomMargin=36,
            )

            styles = getSampleStyleSheet()

            # Custom Typography Styles
            title_style = ParagraphStyle(
                "DocTitle",
                parent=styles["Heading1"],
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#0F172A"),
                fontName="Helvetica-Bold",
            )

            section_heading = ParagraphStyle(
                "SectionHeading",
                parent=styles["Heading2"],
                fontSize=12,
                leading=16,
                textColor=colors.HexColor("#1E3A8A"),
                fontName="Helvetica-Bold",
                spaceAfter=6,
            )

            body_text = ParagraphStyle(
                "BodyDark",
                parent=styles["Normal"],
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#334155"),
                fontName="Helvetica",
            )

            body_bold = ParagraphStyle(
                "BodyDarkBold",
                parent=body_text,
                fontName="Helvetica-Bold",
            )

            table_header = ParagraphStyle(
                "TableHeader",
                parent=styles["Normal"],
                fontSize=8.5,
                leading=11,
                textColor=colors.white,
                fontName="Helvetica-Bold",
            )

            table_cell = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontSize=8,
                leading=10.5,
                textColor=colors.HexColor("#1E293B"),
                fontName="Helvetica",
            )

            table_cell_bold = ParagraphStyle(
                "TableCellBold",
                parent=table_cell,
                fontName="Helvetica-Bold",
            )

            callout_text = ParagraphStyle(
                "CalloutText",
                parent=styles["Normal"],
                fontSize=8.5,
                leading=11.5,
                textColor=colors.HexColor("#991B1B"),
                fontName="Helvetica",
            )

            story = []

            # 1. Header Banner
            story.append(Paragraph("ENTERPRISE AI RISK ASSESSMENT REPORT", title_style))
            meta_line = (
                f"<b>Analysis ID:</b> {analysis.analysis_id[:8]}... | "
                f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | "
                f"<b>Framework:</b> ISO 31000 Multi-Factor"
            )
            story.append(Paragraph(meta_line, body_text))
            story.append(Spacer(1, 8))
            story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2563EB"), spaceAfter=12))

            # 2. Overall Risk Banner
            severity_colors = {
                "LOW": "#16A34A",
                "MEDIUM": "#CA8A04",
                "HIGH": "#EA580C",
                "CRITICAL": "#DC2626",
            }
            color_hex = severity_colors.get(analysis.overall_risk.value, "#DC2626")
            
            banner_text = (
                f"<font color='{color_hex}'><b>OVERALL RISK SEVERITY: {analysis.overall_risk.value} "
                f"(Composite Score: {analysis.overall_score:.1f}/5.0)</b></font>"
            )
            story.append(Paragraph(banner_text, section_heading))
            story.append(Spacer(1, 4))

            # 3. Executive Summary
            story.append(Paragraph("Executive Summary", section_heading))
            story.append(Paragraph(analysis.executive_summary, body_text))
            story.append(Spacer(1, 10))

            # 4. Conflicts & Contradictions Warning (if detected)
            if analysis.conflicts_detected:
                story.append(Paragraph("<b>⚠️ Contradictions & Conflict Warnings Detected:</b>", section_heading))
                for conflict in analysis.conflicts_detected:
                    story.append(Paragraph(f"• {conflict}", callout_text))
                story.append(Spacer(1, 10))

            # 5. Identified Risk Breakdown Table (with auto-wrapped Paragraphs)
            story.append(Paragraph(f"Identified Risk Vectors ({len(analysis.identified_risks)})", section_heading))
            
            risk_table_rows = [
                [
                    Paragraph("Category", table_header),
                    Paragraph("Severity & Score", table_header),
                    Paragraph("Risk Description & Root Cause", table_header),
                    Paragraph("Verifiable Evidence Citation", table_header),
                ]
            ]

            for r in analysis.identified_risks:
                sev_color = severity_colors.get(r.severity.value, "#DC2626")
                evidence_lines = []
                for source in r.sources[:2]:
                    if source.source_type == "Document":
                        location = f"{source.document_name or 'Document'} | Page {source.page_number or '?'} | Section {source.section or 'General'} | Paragraph {source.paragraph_number or '?'}"
                        evidence_lines.append(f"<b>Source:</b> {location}<br/><i>\"{source.exact_quote}\"</i>")
                    else:
                        evidence_lines.append(f"<b>Source:</b> User Input<br/><i>\"{source.exact_quote}\"</i>")
                ev_str = "<br/><br/>".join(evidence_lines) if evidence_lines else "No evidence source available"

                risk_table_rows.append([
                    Paragraph(f"<b>{r.category.value}</b>", table_cell_bold),
                    Paragraph(
                        f"<font color='{sev_color}'><b>{r.severity.value}</b></font><br/>"
                        f"Impact: {r.impact_rating:.1f}/5<br/>Probability: {r.probability_rating:.1f}/5<br/>"
                        f"Urgency: {r.urgency_rating:.1f}/5<br/>Evidence: {r.evidence_quality_rating:.1f}/5<br/>"
                        f"Final: {r.numerical_score:.1f}/5.0<br/>Confidence: {r.confidence_level.value}",
                        table_cell,
                    ),
                    Paragraph(f"<b>{r.title}</b><br/>{r.description}<br/><i>Root Cause: {r.root_cause}</i>", table_cell),
                    Paragraph(ev_str, table_cell),
                ])

            # Explicit column widths totaling 540pt (letter width 612 - 72pt margins = 540pt)
            risk_table = Table(risk_table_rows, colWidths=[110, 80, 210, 140])
            risk_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.append(risk_table)
            story.append(Spacer(1, 14))

            # 6. Priority Mitigation Actions Table
            story.append(Paragraph("Actionable Mitigation & Decision Plan", section_heading))
            action_table_rows = [
                [
                    Paragraph("#", table_header),
                    Paragraph("Mitigation Action", table_header),
                    Paragraph("Owner", table_header),
                    Paragraph("Deadline", table_header),
                    Paragraph("Expected Outcome", table_header),
                ]
            ]

            for idx, act in enumerate(analysis.priority_actions, 1):
                action_table_rows.append([
                    Paragraph(str(idx), table_cell_bold),
                    Paragraph(f"<b>[{act.priority.value}]</b> {act.action}", table_cell),
                    Paragraph(act.owner, table_cell_bold),
                    Paragraph(act.deadline, table_cell),
                    Paragraph(act.expected_outcome, table_cell),
                ])

            action_table = Table(action_table_rows, colWidths=[20, 230, 95, 65, 130])
            action_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0FDFA")]),
            ]))
            story.append(action_table)
            story.append(Spacer(1, 14))

            # 7. Anti-Hallucination Missing Information Matrix
            if analysis.missing_breakdown:
                story.append(Paragraph("Missing Information & Uncertainty Matrix", section_heading))
                story.append(Paragraph("<b>Known Verified Facts:</b>", body_bold))
                for fact in analysis.missing_breakdown.known_facts[:3]:
                    story.append(Paragraph(f"  ✓ {fact}", body_text))

                story.append(Spacer(1, 4))
                story.append(Paragraph("<b>Required for Full Assessment:</b>", body_bold))
                for needed in analysis.missing_breakdown.needed_to_assess_accurately[:3]:
                    story.append(Paragraph(f"  ? {needed}", body_text))
                story.append(Spacer(1, 10))

            # 8. Final deterministic quality-control result
            if analysis.report_validation:
                status = "PASSED" if analysis.report_validation.passed else "REVIEW REQUIRED"
                story.append(Paragraph(f"Report Quality Control: {status}", section_heading))
                story.append(Paragraph(
                    f"Fact-to-risk coverage: {analysis.report_validation.fact_to_risk_coverage:.0%}. "
                    "Checks: evidence traceability, risk-to-action mapping, ranking, duplicate consolidation, and uncertainty reconciliation.",
                    body_text,
                ))
                for warning in analysis.report_validation.warnings[:4]:
                    story.append(Paragraph(f"• {warning}", callout_text))
                story.append(Spacer(1, 10))

            # 9. Audit Trail & Legal Disclaimer
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94A3B8"), spaceAfter=8))
            disclaimer = (
                "<b>Audit & Legal Notice:</b> This automated risk assessment report was compiled by the AI Risk Analyst decision-support engine. "
                "All severity ratings are derived deterministically using multi-factor mathematical models. Ratings and recommendations must be validated by "
                "qualified enterprise risk officers before formal governance execution."
            )
            story.append(Paragraph(disclaimer, ParagraphStyle("Disc", parent=styles["Normal"], fontSize=7, leading=9, textColor=colors.HexColor("#64748B"))))

            doc.build(story)
            return buffer.getvalue()

        except Exception as e:
            # Fallback plain text report if ReportLab has rendering issues
            plain_report = (
                f"ENTERPRISE RISK ASSESSMENT REPORT\n"
                f"Overall Risk Severity: {analysis.overall_risk.value} (Score: {analysis.overall_score}/5.0)\n\n"
                f"Executive Summary:\n{analysis.executive_summary}\n\n"
                f"Identified Risks:\n"
            )
            for r in analysis.identified_risks:
                plain_report += f"- [{r.category.value}] {r.title} ({r.severity.value})\n  Impact: {r.potential_impact}\n\n"
            return plain_report.encode("utf-8")

        finally:
            buffer.close()


# Global PDF Generator Singleton
pdf_generator_service = PDFReportGeneratorService()
