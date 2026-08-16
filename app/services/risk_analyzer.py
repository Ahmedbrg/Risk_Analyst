"""
AI Risk Analyst — Core Grounded Risk Analysis Engine with Zero-Hallucination & Deterministic Scoring.
"""

import json
import re
import time
import uuid
from typing import List, Dict, Any, Tuple, Optional

from app.config import settings
from app.schemas.risk import (
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    IdentifiedRisk,
    ActionableRecommendation,
    EvidenceSource,
    MissingInformationBreakdown,
    RiskDependency,
    ReportValidation,
    ExtractedFactSchema,
    RiskTaxonomyCategory,
    RiskSeverity,
    ConfidenceLevel,
)
from app.core.methodology import RiskScoringMethodology, ConflictDetector, RiskDeduplicator
from app.core.quality import RiskReportQualityGate
from app.core.facts import ExtractedFact, FactExtractor
from app.core.fact_validation import FactValidationResult, FactValidator
from app.core.security import security_sanitizer, audit_logger
from app.core.memory import memory_manager
from app.services.rag_service import rag_service


class AIRiskAnalyzerService:
    """
    Production-Grade AI Risk Analysis Engine.
    Guarantees:
    - 0% Hallucinated metrics / figures
    - 100% Deterministic & Explainable Severity Matrix
    - Traceable Evidence with Document / User Input Citations
    - PII Masking, Prompt Injection Defense, and Conflict Detection
    """

    def analyze_situation(
        self,
        request: RiskAnalysisRequest,
        additional_context: str = "",
    ) -> RiskAnalysisResponse:
        start_time = time.time()
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # 1. Security Sanitization (PII Masking & Prompt Injection Check)
        clean_situation, security_warnings = security_sanitizer.sanitize_input(request.situation)

        # 2. Conversation & RAG Context Assembly
        history_context = memory_manager.get_context_prompt(conversation_id)
        
        # Ingest RAG context if requested
        rag_context = ""
        rag_sources: List[EvidenceSource] = []
        if request.include_rag:
            rag_res = rag_service.retrieve_relevant_context(clean_situation, top_k=3)
            rag_context = rag_res.grounded_context
            for chunk in rag_res.retrieved_chunks:
                rag_sources.append(EvidenceSource(
                    source_type="Document",
                    document_name=chunk.filename,
                    page_number=chunk.page_number,
                    section=chunk.section_title,
                    paragraph_number=chunk.paragraph_index,
                    # A citation must remain verbatim; an ellipsis would make it
                    # impossible for the quality gate to verify the quote.
                    exact_quote=chunk.content[:150],
                ))

        combined_context = (history_context + "\n" + additional_context + "\n" + rag_context + "\n" + clean_situation).strip()

        # Fact extraction and validation are explicit pipeline stages before
        # risk detection. Only these source-backed statements are allowed to
        # drive the deterministic detector or appear in coverage measurement.
        grounded_evidence = "\n".join([clean_situation] + [source.exact_quote for source in rag_sources])
        extracted_facts = FactExtractor.extract(grounded_evidence)
        fact_validation = FactValidator.validate(extracted_facts)

        # 3. Conflict & Contradiction Detection
        conflicts = ConflictDetector.detect_conflicts(clean_situation, history_context)
        conflicts.extend(ConflictDetector.detect_document_conflicts(rag_sources))

        # 4. Engine Decision: LLM vs Rule-Based Fallback
        has_llm_key = bool(settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY)

        if has_llm_key:
            try:
                response = self._analyze_with_llm(
                    clean_situation, combined_context, conversation_id, start_time,
                    security_warnings, conflicts, rag_sources, extracted_facts, fact_validation, request.use_crew_ai
                )
            except Exception as e:
                print(f"[Warning] LLM analysis failed: {e}. Falling back to Rule-Based Engine.")
                response = self._analyze_with_rules(
                    clean_situation, combined_context, conversation_id, start_time,
                    security_warnings, conflicts, rag_sources, extracted_facts, fact_validation, request.use_crew_ai
                )
        else:
            response = self._analyze_with_rules(
                clean_situation, combined_context, conversation_id, start_time,
                security_warnings, conflicts, rag_sources, extracted_facts, fact_validation, request.use_crew_ai
            )

        # 5. Audit Logging
        audit_logger.record_event(
            event_type="RISK_AUDIT_COMPLETED",
            user_or_session_id=conversation_id,
            model_used=response.analysis_methodology,
            input_summary=clean_situation,
            overall_risk=response.overall_risk.value,
            risks_detected=[r.category.value for r in response.identified_risks],
            execution_time_seconds=response.execution_time_seconds,
            security_warnings=security_warnings,
        )

        return response

    def _analyze_with_llm(
        self,
        situation: str,
        combined_context: str,
        conversation_id: str,
        start_time: float,
        security_warnings: List[str],
        conflicts: List[str],
        rag_sources: List[EvidenceSource],
        extracted_facts: List[ExtractedFact],
        fact_validation: FactValidationResult,
        use_crew_ai: bool = False,
    ) -> RiskAnalysisResponse:
        from openai import OpenAI

        if settings.OPENROUTER_API_KEY:
            client = OpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "http://localhost:8001",
                    "X-Title": "AI Risk Analyst",
                },
            )
            model_name = settings.LLM_MODEL or "openrouter/free"
        else:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            model_name = settings.LLM_MODEL or "gpt-4o-mini"

        system_prompt = """You are an expert Enterprise AI Risk Analyst. Analyze the user's business situation and produce a rigorous JSON assessment.

STRICT ZERO-HALLUCINATION PRODUCT PRINCIPLES:
1. ONLY cite facts, metrics, and percentages explicitly present in the input or documents. DO NOT INVENT numbers (e.g. do not invent "15-20% revenue drop" or "3-6 months cash" unless explicitly provided).
2. For any unknown information, place it explicitly in "missing_information" / "needed_to_assess_accurately".
3. MAP TO THE FIXED 10 TAXONOMY DOMAINS:
   - "Financial Risk"
   - "Operational Risk"
   - "Cybersecurity Risk"
   - "Legal / Compliance Risk"
   - "Supplier Risk"
   - "Customer Risk"
   - "Strategic Risk"
   - "HR / Workforce Risk"
   - "Reputational Risk"
   - "Technology Risk"
4. For each risk, evaluate numerical sub-scores (1.0 to 5.0):
   - impact_rating (1-5)
   - probability_rating (1-5)
   - urgency_rating (1-5)
   - evidence_quality (1-5)
   - root_cause and contributing_factors
5. Provide actionable recommendations with an Owner. Only provide a numerical deadline or target when it appears explicitly in the input or documents; otherwise use "Deadline to be confirmed".

Return valid JSON adhering to this exact schema:
{
  "executive_summary": "...",
  "identified_risks": [
    {
      "category": "Financial Risk",
      "impact_rating": 4.5,
      "probability_rating": 4.0,
      "urgency_rating": 4.0,
      "evidence_quality": 4.5,
      "title": "...",
      "description": "...",
      "root_cause": "...",
      "contributing_factors": ["..."],
      "potential_impact": "...",
      "exact_quotes": ["..."],
      "recommendations": [
        {
          "action": "...",
          "priority": "HIGH",
          "owner": "CFO",
          "deadline": "Deadline to be confirmed",
          "expected_outcome": "..."
        }
      ],
      "unknown_aspects": ["..."],
      "needed_to_assess": ["..."]
    }
  ],
  "known_facts": ["..."],
  "unknown_aspects": ["..."],
  "needed_to_assess_accurately": ["..."],
  "follow_up_questions": ["..."]
}"""

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Validated source facts only:\n" + "\n".join(
                    f"[{fact.fact_id}] {fact.source_text}" for fact in extracted_facts
                    if fact.fact_id not in set(fact_validation.invalid_fact_ids)
                )},
            ],
            temperature=0.1,
            timeout=8.0,
        )

        content = response.choices[0].message.content or "{}"
        cleaned_json = content.strip()
        if cleaned_json.startswith("```"):
            cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

        data = json.loads(cleaned_json)
        # LLM findings can only use user input and retrieved document excerpts
        # as evidence.  Memory and supplementary prompt context are not a
        # citable source for a new finding.
        evidence_context = "\n".join([situation] + [source.exact_quote for source in rag_sources])
        self._validate_llm_payload(data, evidence_context)
        return self._post_process_findings(
            data, situation, conversation_id, start_time,
            f"LLM Reasoning ({model_name}) + Deterministic Scoring Matrix",
            security_warnings, conflicts, rag_sources, use_crew_ai, extracted_facts, fact_validation
        )

    @staticmethod
    def _validate_llm_payload(data: Any, grounded_context: str) -> None:
        """Schema and grounding gate between LLM JSON and business-rule scoring."""
        if not isinstance(data, dict) or not isinstance(data.get("identified_risks"), list):
            raise ValueError("LLM output must be an object containing an identified_risks list")

        allowed_categories = {category.value for category in RiskTaxonomyCategory}
        context = grounded_context.lower()
        for finding in data["identified_risks"]:
            if not isinstance(finding, dict):
                raise ValueError("Each LLM risk finding must be a JSON object")
            if finding.get("category") not in allowed_categories:
                raise ValueError("LLM finding contains an unsupported risk taxonomy category")
            for key in ("impact_rating", "probability_rating", "urgency_rating", "evidence_quality"):
                value = finding.get(key)
                if not isinstance(value, (int, float)) or not 1 <= value <= 5:
                    raise ValueError(f"LLM finding has invalid {key}")
            quotes = finding.get("exact_quotes", [])
            if not isinstance(quotes, list) or not quotes:
                raise ValueError("LLM finding requires at least one evidence quote")
            if any(str(quote).lower() not in context for quote in quotes):
                raise ValueError("LLM finding contains unsupported evidence")
            for claim_key in ("root_cause", "potential_impact"):
                claim = str(finding.get(claim_key, ""))
                if claim and not RiskReportQualityGate.claim_is_supported_or_qualified(claim, quotes):
                    raise ValueError(f"LLM finding contains unsupported {claim_key}")
            for recommendation in finding.get("recommendations", []):
                if not isinstance(recommendation, dict):
                    raise ValueError("LLM recommendation must be a JSON object")
                recommendation_text = " ".join(str(value) for value in recommendation.values()).lower()
                for number in re.findall(r"\b\d+(?:\.\d+)?\b", recommendation_text):
                    if number not in context:
                        raise ValueError("LLM recommendation contains an unsupported numerical claim")

    def _analyze_with_rules(
        self,
        situation: str,
        combined_context: str,
        conversation_id: str,
        start_time: float,
        security_warnings: List[str],
        conflicts: List[str],
        rag_sources: List[EvidenceSource],
        extracted_facts: List[ExtractedFact],
        fact_validation: FactValidationResult,
        use_crew_ai: bool = False,
    ) -> RiskAnalysisResponse:
        """
        Deterministic Rule-Based Intelligence Engine.
        Extracts verified facts, detects risk vectors, and applies 5-factor scoring.
        """
        # Only user text and retrieved document excerpts are eligible for
        # deterministic extraction.  Conversation/system context is deliberately
        # excluded because it cannot be cited as evidence for a new risk.
        invalid_fact_ids = set(fact_validation.invalid_fact_ids)
        grounded_input = "\n".join(
            fact.source_text for fact in extracted_facts if fact.fact_id not in invalid_fact_ids
        )
        sit_lower = grounded_input.lower()
        # Keep supplied statements verbatim across normal sentence separators so
        # every extracted fact can be traced back to the user input.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", grounded_input) if len(s.strip()) > 5]
        # A sanitized adversarial instruction is neither a business fact nor
        # risk evidence.  Removing it here prevents prompt text leaking into
        # facts, risk titles, citations, and the final report.
        sentences = [sentence for sentence in sentences if "[redacted_adversarial_instruction]" not in sentence.lower()]
        
        # Facts remain verbatim. Any generated interpretation is kept separately
        # in `inferences` and never presented as an input fact.
        known_facts: List[str] = sentences.copy()
        inferences: List[str] = []
        raw_risks: List[Dict[str, Any]] = []
        unknowns: List[str] = []
        needed: List[str] = []

        # 1. Financial Risk Vector
        financial_terms = ["revenue", "decrease", "decline", "loss", "cash", "reserves", "debt", "margin", "profit", "burn", "price hike", "price increase"]
        cash_terms = ["cash runway", "cash reserves", "liquidity", "burn rate", "cash balance"]
        if any(w in sit_lower for w in financial_terms):
            ev_quotes = [s for s in sentences if any(w in s.lower() for w in ["revenue", "cash", "loss", "decline", "debt", "reserves", "margin", "cost"])] or [situation]
            inferences.append("Declining financial reserves threaten operational sustainability and debt servicing.")
            unknowns.extend(["Current monthly burn rate", "Exact runway in months"])
            needed.extend(["Current cash runway", "Monthly burn rate", "Debt obligations and maturity schedule"])

            raw_risks.append({
                "category": RiskTaxonomyCategory.FINANCIAL,
                "impact": 4.0 if any(w in sit_lower for w in ["price hike", "price increase"]) else (4.5 if any(w in sit_lower for w in ["reserves", "cash runway", "30%", "35%", "40%"]) else 4.0),
                "probability": 4.2,
                "urgency": 4.0,
                "evidence_quality": 4.5,
                "title": "Cash Runway and Liquidity Exposure" if any(w in sit_lower for w in cash_terms) else "Financial Performance Exposure",
                "description": "Reported financial condition may constrain the organisation's ability to fund operations.",
                "root_cause": "Reported financial condition; underlying cause is not established.",
                "contributing_factors": [],
                "potential_impact": "Reduced capacity to fund operations or meet financial commitments.",
                "quotes": ev_quotes,
                "recommendations": [
                    {
                        "action": "Prepare a short-term cash-flow forecast and review non-essential operating expenditure.",
                        "priority": RiskSeverity.HIGH,
                        "owner": "CFO / Finance Director",
                        "deadline": "Near-term review",
                        "expected_outcome": "Improve visibility of liquidity exposure and available mitigation options.",
                    },
                    {
                        "action": "Engage lenders for temporary revolving credit line buffer.",
                        "priority": RiskSeverity.HIGH,
                        "owner": "Treasury",
                        "deadline": "Planned follow-up",
                        "expected_outcome": "Assess available liquidity-contingency options.",
                    }
                ],
                "unknowns": ["Current cash runway", "Monthly burn rate", "Debt obligations"],
                "needed": ["Current cash runway", "Monthly burn rate", "Debt obligations and maturity schedule"],
            })

        if any(w in sit_lower for w in ["cost increase", "price increase", "price hike", "margin decline", "margin decreased", "margin fell"]):
            cost_quotes = [s for s in sentences if any(w in s.lower() for w in ["cost increase", "price increase", "price hike", "margin decline", "margin decreased", "margin fell"])]
            raw_risks.append({
                "category": RiskTaxonomyCategory.FINANCIAL, "dedupe_key": "cost-and-margin",
                "impact": 4.0, "probability": 3.8, "urgency": 3.5, "evidence_quality": 4.5,
                "title": "Cost Increase and Margin Compression Exposure",
                "description": "Reported cost or margin movement may reduce financial performance.",
                "root_cause": "Reported cost increase or margin change; drivers are not established.", "contributing_factors": [],
                "potential_impact": "Potential pressure on margins, pricing, or operating cash generation.", "quotes": cost_quotes,
                "recommendations": [{"action": "Validate the reported cost and margin movement in the current forecast.", "priority": RiskSeverity.HIGH, "owner": "To be assigned", "deadline": "Priority review", "expected_outcome": "Quantify the verified margin and cash-flow exposure."}],
                "unknowns": ["Cost-driver breakdown", "Pricing pass-through capability"],
                "needed": ["Current cost forecast", "Gross-margin bridge", "Pricing and volume analysis"],
            })

        # 2. Supplier Risk Vector
        supplier_terms = ["supplier", "vendor", "provider", "logistics", "shipping", "delivery", "shipments", "lead times"]
        if any(w in sit_lower for w in supplier_terms) or ("late" in sit_lower and "deliver" in sit_lower):
            ev_quotes = [s for s in sentences if any(w in s.lower() for w in ["supplier", "late", "delay", "vendor", "inventory", "capacity", "shipments"])] or [situation]
            inferences.append("Repeated supplier delays create fulfillment bottlenecks and customer SLA breach exposure.")
            unknowns.extend(["SLA penalty clauses in vendor contracts", "Availability of alternative second-source suppliers"])
            needed.extend(["Vendor SLA compliance logs", "Inventory buffer status"])

            raw_risks.append({
                "category": RiskTaxonomyCategory.SUPPLIER,
                "impact": 5.0 if any(w in sit_lower for w in ["bankruptcy", "halted all"]) else 3.8,
                "probability": 4.8 if any(w in sit_lower for w in ["bankruptcy", "halted all"]) else 4.0,
                "urgency": 5.0 if any(w in sit_lower for w in ["bankruptcy", "halted all"]) else 3.8,
                "evidence_quality": 4.5,
                "title": "Critical Supplier Schedule Slippage & Single-Source Dependency",
                "description": "Chronic supplier fulfillment delays endanger customer delivery commitments.",
                "root_cause": "Reported supplier delivery delays; underlying cause is not established.",
                "contributing_factors": [],
                "potential_impact": "Delayed fulfilment or unmet delivery commitments.",
                "quotes": ev_quotes,
                "recommendations": [
                    {
                        "action": "Audit vendor SLA non-compliance and enforce contractual penalty provisions.",
                        "priority": RiskSeverity.HIGH,
                        "owner": "Head of Procurement",
                        "deadline": "Near-term review",
                        "expected_outcome": "Establish the supplier's current delivery exposure and available remedies.",
                    },
                    {
                        "action": "Qualify and onboard secondary backup suppliers.",
                        "priority": RiskSeverity.HIGH,
                        "owner": "Supply Chain Lead",
                        "deadline": "Planned follow-up",
                        "expected_outcome": "Reduce dependency on a single supplier where alternatives are viable.",
                    }
                ],
                "unknowns": ["SLA terms", "Supplier dependency percentage", "Availability of backup suppliers"],
                "needed": ["SLA terms", "Supplier dependency percentage", "Qualified backup suppliers"],
            })

            # Supplier disruption can be an independent operational vector when
            # the input explicitly identifies production or shipment impact.
            if any(w in sit_lower for w in ["manufacturing", "production", "halted", "shipments"]):
                raw_risks.append({
                    "category": RiskTaxonomyCategory.OPERATIONAL, "impact": 4.0, "probability": 3.5, "urgency": 3.8, "evidence_quality": 4.5,
                    "title": "Supplier-Driven Operational Continuity Exposure",
                    "description": "Reported supplier disruption directly affects an identified operating activity.",
                    "root_cause": "Reported supplier disruption.", "contributing_factors": [],
                    "potential_impact": "Interruption to the referenced production, manufacturing, or shipment activity.", "quotes": ev_quotes,
                    "recommendations": [{"action": "Validate affected operating capacity and activate the documented supplier-contingency process.", "priority": RiskSeverity.HIGH, "owner": "Operations Lead", "deadline": "Priority review", "expected_outcome": "Establish the immediate operating impact and available continuity actions."}],
                    "unknowns": ["Affected operating capacity"], "needed": ["Current production or shipment status", "Supplier contingency plan"],
                })

        # 3. Legal / Compliance Risk Vector
        if any(w in sit_lower for w in ["contract", "expire", "expiration", "agreement", "legal", "clause", "term", "gdpr", "compliance", "formal notice", "intellectual property", "lawsuit", "litigation"]):
            ev_quotes = [s for s in sentences if any(w in s.lower() for w in ["contract", "expire", "expiration", "agreement", "gdpr"])] or [situation]
            inferences.append("Expiring primary contracts present revenue cliff or liability exposure without renewal.")
            unknowns.extend(["Contract renewal notice window", "Client willingness to renew"])
            needed.extend(["Master Service Agreement terms and notice deadlines"])

            raw_risks.append({
                "category": RiskTaxonomyCategory.LEGAL_COMPLIANCE,
                "impact": 4.2 if any(w in sit_lower for w in ["expire", "expiration"]) else 4.0,
                "probability": 3.8,
                "urgency": 4.5 if any(w in sit_lower for w in ["expire", "expiration"]) else 3.5,
                "evidence_quality": 4.5,
                "title": "Impending Contract Expiration & Renewal Exposure",
                "description": "Crucial client or supplier contract reaching expiration without finalized renewal terms.",
                "root_cause": "Reported contract-expiry timeline.",
                "contributing_factors": [],
                "potential_impact": "Loss of contractual rights, revenue, or service continuity if the contract is not renewed.",
                "quotes": ev_quotes,
                "recommendations": [
                    {
                        "action": "Initiate executive renewal negotiations with counterparty leadership.",
                        "priority": RiskSeverity.CRITICAL,
                        "owner": "General Counsel / Account Director",
                        "deadline": "Immediate review",
                        "expected_outcome": "Clarify renewal status and reduce avoidable contract-expiry exposure.",
                    }
                ],
                "unknowns": ["Renewal terms", "Notice period", "Termination clauses"],
                "needed": ["Renewal terms", "Notice period", "Termination clauses"],
            })

        # 4. Cybersecurity Risk Vector
        if any(w in sit_lower for w in ["ransomware", "infected", "data breach", "cyber", "security", "personal data", "exposed", "hack", "virus", "cve", "patch", "vulnerability"]):
            ev_quotes = [s for s in sentences if any(w in s.lower() for w in ["ransomware", "infected", "breach", "security", "patch", "vulnerability", "personal data", "exposed"])] or [situation]
            no_confirmed_breach = any(phrase in sit_lower for phrase in ["no confirmed data breach", "no data breach", "breach not confirmed"])
            active_cyber_incident = not no_confirmed_breach and any(
                w in sit_lower for w in ["ransomware", "infected", "data breach", "exposed", "hack", "virus"]
            )
            severe_cyber_exposure = active_cyber_incident or any(
                w in sit_lower for w in ["zero-day", "critical vulnerability"]
            )
            if active_cyber_incident:
                inferences.append("A reported cybersecurity event may require containment and impact assessment.")
                cyber_title = "Confirmed Cybersecurity Incident Exposure"
                cyber_description = "Reported cybersecurity event requires verified containment and impact assessment."
                cyber_actions = [
                    {"action": "Verify incident scope and execute the documented incident-response process.", "priority": RiskSeverity.CRITICAL, "owner": "To be assigned", "deadline": "Immediate containment review", "expected_outcome": "Establish verified incident scope and containment status."},
                    {"action": "Assess whether notification obligations apply using verified incident facts.", "priority": RiskSeverity.HIGH, "owner": "To be assigned", "deadline": "Priority legal review", "expected_outcome": "Determine applicable notification obligations."},
                ]
                cyber_unknowns = ["Scope of affected systems", "Scope of affected data"]
                cyber_needed = ["Forensic incident report", "System and access logs"]
            else:
                inferences.append("Reported security conditions may increase exposure; no breach or compromise is assumed.")
                cyber_title = "Cybersecurity Vulnerability / Security Incident Exposure"
                cyber_description = "Reported security incidents, patch gaps, or vulnerabilities require verification; no breach is assumed."
                cyber_actions = [
                    {"action": "Verify the reported security incidents and affected assets without assuming compromise.", "priority": RiskSeverity.HIGH, "owner": "To be assigned", "deadline": "Priority review", "expected_outcome": "Establish the verified incident and exposure scope."},
                    {"action": "Review patch status for the reported assets and prioritise remediation from verified exposure evidence.", "priority": RiskSeverity.HIGH, "owner": "To be assigned", "deadline": "Priority remediation review", "expected_outcome": "Produce an evidence-based patch remediation plan."},
                ]
                cyber_unknowns = ["Whether a breach occurred", "Affected asset scope", "Exploitability of reported vulnerabilities"]
                cyber_needed = ["Incident records", "Asset inventory", "Patch-status evidence", "Recent vulnerability assessment"]
            raw_risks.append({
                "category": RiskTaxonomyCategory.CYBERSECURITY,
                "impact": 5.0 if severe_cyber_exposure else 4.0,
                "probability": 4.8 if severe_cyber_exposure else 3.5,
                "urgency": 5.0 if severe_cyber_exposure else 3.8,
                "evidence_quality": 4.8,
                "title": cyber_title,
                "description": cyber_description,
                "root_cause": "Reported cybersecurity incident; technical cause is unconfirmed.",
                "contributing_factors": [],
                "potential_impact": "Operational disruption, data-protection obligations, and reputational harm.",
                "quotes": ev_quotes,
                "recommendations": cyber_actions,
                "unknowns": cyber_unknowns,
                "needed": cyber_needed,
            })

        # 5. HR / Workforce Risk Vector
        if any(w in sit_lower for w in ["resigned", "resignation", "turnover", "architect", "engineer", "staff", "quit", "leave"]):
            ev_quotes = [s for s in sentences if any(w in s.lower() for w in ["resigned", "architect", "engineer", "staff", "quit"])] or [situation]
            inferences.append("Key technical personnel departure directly threatens mission-critical project milestones.")
            unknowns.extend(["Knowledge documentation state", "Notice period duration remaining"])
            needed.extend(["Handover transition plan and talent backfill pipeline"])

            raw_risks.append({
                "category": RiskTaxonomyCategory.HR,
                "impact": 4.0,
                "probability": 4.2,
                "urgency": 4.0,
                "evidence_quality": 4.5,
                "title": "Key Technical Talent Departure & Project Delivery Disruption",
                "description": "Resignation of core architects or engineers during active delivery commitments.",
                "root_cause": "Reported departure of key personnel.",
                "contributing_factors": [],
                "potential_impact": "Missed delivery deadlines, SLA penalties, and knowledge loss.",
                "quotes": ev_quotes,
                "recommendations": [
                    {
                        "action": "Implement mandatory structured daily technical knowledge transfer sessions.",
                        "priority": RiskSeverity.HIGH,
                        "owner": "Engineering Manager",
                        "deadline": "Immediate review",
                        "expected_outcome": "Document architecture decisions and system runbooks.",
                    },
                    {
                        "action": "Contract senior specialist contractors to bridge capacity shortfall.",
                        "priority": RiskSeverity.HIGH,
                        "owner": "VP of Engineering / HR",
                        "deadline": "Planned follow-up",
                        "expected_outcome": "Protect delivery timeline.",
                    }
                ],
                "unknowns": ["Availability of internal successors"],
                "needed": ["Handover checklist sign-off"],
            })

        # 6. Technology and operational resilience
        if any(w in sit_lower for w in ["datacenter", "downtime", "backup", "migration", "outage", "system failure", "api", "product bugs"]):
            critical_incident = any(w in sit_lower for w in ["datacenter", "downtime", "outage", "failed to restore"])
            rating = 4.8 if critical_incident else 3.0
            quotes = [s for s in sentences if any(w in s.lower() for w in ["datacenter", "downtime", "backup", "migration", "outage", "api", "bugs"])] or [situation]
            raw_risks.append({
                "category": RiskTaxonomyCategory.TECHNOLOGY, "impact": rating, "probability": rating,
                "urgency": rating, "evidence_quality": 4.5, "title": "Technology Resilience and Service Continuity Exposure",
                "description": "Reported technology conditions may disrupt service continuity or planned delivery.",
                "root_cause": "Reported infrastructure, software, or migration condition", "contributing_factors": [],
                "potential_impact": "Service disruption, delayed delivery, or impaired data recovery.", "quotes": quotes,
                "recommendations": [{"action": "Verify recovery status and service-continuity controls.", "priority": RiskSeverity.HIGH, "owner": "Technology Lead", "deadline": "Deadline to be confirmed", "expected_outcome": "Establish the verified operational impact and recovery options."}],
                "unknowns": ["Affected systems", "Recovery status", "Business-service dependency"],
                "needed": ["Incident timeline", "Backup and recovery evidence", "Service dependency map"],
            })
            raw_risks.append({
                "category": RiskTaxonomyCategory.OPERATIONAL, "impact": rating, "probability": rating - 0.2,
                "urgency": rating, "evidence_quality": 4.5, "title": "Operational Delivery Disruption",
                "description": "The reported condition may interrupt operational delivery.", "root_cause": "Technology or process disruption",
                "contributing_factors": [], "potential_impact": "Unmet service commitments and delivery disruption.", "quotes": quotes,
                "recommendations": [{"action": "Identify affected business processes and contingency options.", "priority": RiskSeverity.HIGH, "owner": "Operations Lead", "deadline": "Deadline to be confirmed", "expected_outcome": "Clarify immediate operational exposure."}],
                "unknowns": ["Affected process scope"], "needed": ["Business-continuity plan", "Current operating status"],
            })

        # 7. Customer and reputation exposure
        if any(w in sit_lower for w in ["cancelled", "cancelled", "subscription", "account", "complaint", "boycott", "social media", "twitter"]):
            reputation_signal = any(w in sit_lower for w in ["boycott", "social media", "twitter"])
            rating = 3.0 if reputation_signal else 4.5
            quotes = [s for s in sentences if any(w in s.lower() for w in ["cancelled", "subscription", "account", "complaint", "boycott", "social media", "twitter"])] or [situation]
            raw_risks.append({
                "category": RiskTaxonomyCategory.CUSTOMER, "impact": rating, "probability": rating, "urgency": rating, "evidence_quality": 4.5,
                "dedupe_key": "customer-retention",
                "title": "Customer Retention and Service Experience Exposure", "description": "Reported customer events may affect retention and trust.",
                "root_cause": "Reported cancellations, complaints, or unresolved service issues", "contributing_factors": [], "potential_impact": "Customer loss and reduced recurring revenue.", "quotes": quotes,
                "recommendations": [{"action": "Verify affected customers and address the reported service issue.", "priority": RiskSeverity.HIGH, "owner": "Customer Success Lead", "deadline": "Deadline to be confirmed", "expected_outcome": "Establish an evidence-based customer recovery plan."}],
                "unknowns": ["Affected customer value", "Root cause of customer dissatisfaction"], "needed": ["Customer-impact analysis", "Service incident records"],
            })
            if reputation_signal:
                raw_risks.append({
                    "category": RiskTaxonomyCategory.REPUTATIONAL, "impact": 3.0, "probability": 3.0, "urgency": 3.0, "evidence_quality": 4.5,
                    "title": "Reputational Trust Exposure", "description": "Public discussion may affect stakeholder trust.", "root_cause": "Reported public customer criticism", "contributing_factors": [], "potential_impact": "Reduced brand trust.", "quotes": quotes,
                    "recommendations": [{"action": "Verify the public claims and prepare a factual response.", "priority": RiskSeverity.MEDIUM, "owner": "Communications Lead", "deadline": "Deadline to be confirmed", "expected_outcome": "Ensure communications are grounded in verified facts."}],
                    "unknowns": ["Reach of public discussion"], "needed": ["Verified communications record", "Stakeholder sentiment evidence"],
                })

            if any(w in sit_lower for w in ["cancelled", "canceled", "lost account"]):
                raw_risks.append({
                    "category": RiskTaxonomyCategory.FINANCIAL, "impact": 4.0, "probability": 4.0, "urgency": 4.0, "evidence_quality": 4.5,
                    "title": "Customer-Loss Revenue Exposure", "description": "Reported account cancellations may reduce recurring or contracted revenue.",
                    "root_cause": "Reported customer cancellation.", "contributing_factors": [],
                    "potential_impact": "Reduced revenue continuity from the affected accounts.", "quotes": quotes,
                    "recommendations": [{"action": "Validate cancelled-account revenue exposure and update the current revenue forecast.", "priority": RiskSeverity.HIGH, "owner": "Finance Director", "deadline": "Priority review", "expected_outcome": "Quantify the verified revenue effect and available mitigation options."}],
                    "unknowns": ["Revenue associated with cancelled accounts"], "needed": ["Cancelled-account revenue analysis", "Updated revenue forecast"],
                })

        # Customer concentration is distinct from churn: a retained but highly
        # concentrated customer base can still create material dependency risk.
        concentration_terms = ["customer concentration", "client concentration", "key customer", "key client", "major customer", "major client", "top customer", "top client", "primary customer", "primary client"]
        has_customer_reference = any(term in sit_lower for term in ["customer", "client", "account", "enterprise agreement"])
        has_concentration_signal = any(term in sit_lower for term in concentration_terms) or (
            has_customer_reference and any(term in sit_lower for term in ["depends on", "of revenue", "% of revenue", "percentage of revenue"])
        )
        if has_concentration_signal:
            quotes = [sentence for sentence in sentences if any(term in sentence.lower() for term in concentration_terms + ["of revenue", "total revenue", "largest customers", "depends on", "reduce purchases", "purchase reduction"])] or [situation]
            raw_risks.append({
                "category": RiskTaxonomyCategory.CUSTOMER, "impact": 4.0, "probability": 3.5, "urgency": 3.5, "evidence_quality": 4.5,
                "dedupe_key": "customer-concentration",
                "title": "Customer Concentration and Revenue Dependency Exposure",
                "description": "Reported customer or contract dependency may create a concentrated-revenue exposure.",
                "root_cause": "Reported dependency on a customer, client, or enterprise agreement.", "contributing_factors": [],
                "potential_impact": "A change in the referenced relationship may materially affect revenue continuity.", "quotes": quotes,
                "recommendations": [
                    {"action": "Validate the referenced customer's revenue share, contract status, and renewal scenario.", "priority": RiskSeverity.HIGH, "owner": "Commercial Director", "deadline": "Priority review", "expected_outcome": "Establish the verified concentration exposure and response options."},
                    {"action": "Document an account-retention and revenue-diversification plan for the identified dependency.", "priority": RiskSeverity.MEDIUM, "owner": "Sales Leadership", "deadline": "Planned follow-up", "expected_outcome": "Reduce reliance on the identified relationship where feasible."},
                ],
                "unknowns": ["Verified revenue share", "Renewal likelihood", "Alternative revenue pipeline"],
                "needed": ["Customer revenue concentration analysis", "Contract renewal status", "Qualified pipeline evidence"],
            })

        # 8. Strategic delivery exposure
        if any(w in sit_lower for w in ["migration", "launch", "rollout", "strategy", "fintech"]):
            quotes = [s for s in sentences if any(w in s.lower() for w in ["migration", "launch", "rollout", "strategy", "fintech"])] or [situation]
            raw_risks.append({
                "category": RiskTaxonomyCategory.STRATEGIC, "impact": 3.0, "probability": 3.0, "urgency": 3.0, "evidence_quality": 4.0,
                "title": "Strategic Delivery and Roadmap Exposure", "description": "Reported delivery delays may affect strategic commitments.", "root_cause": "Reported project or rollout delay", "contributing_factors": [], "potential_impact": "Delayed strategic objectives.", "quotes": quotes,
                "recommendations": [{"action": "Validate roadmap dependencies and decision points.", "priority": RiskSeverity.MEDIUM, "owner": "Programme Sponsor", "deadline": "Deadline to be confirmed", "expected_outcome": "Establish verified options for the strategic plan."}],
                "unknowns": ["Critical roadmap dependencies"], "needed": ["Approved delivery plan", "Dependency register"],
            })

        # 9. Fallback General Uncertainty
        if not raw_risks:
            raw_risks.append({
                "category": RiskTaxonomyCategory.STRATEGIC,
                "impact": 2.5,
                "probability": 2.5,
                "urgency": 2.5,
                "evidence_quality": 2.0,
                "title": "Operational Ambiguity & Information Scarcity",
                "description": "The described scenario contains broad uncertainty requiring quantitative elaboration.",
                "root_cause": "Sparse initial problem description",
                "contributing_factors": ["Absence of specific metrics"],
                "potential_impact": "Sub-optimal decision prioritization.",
                "quotes": sentences[:1],
                "recommendations": [
                    {
                        "action": "Provide specific financial metrics, contract dates, or vendor names.",
                        "priority": RiskSeverity.MEDIUM,
                        "owner": "Risk Lead",
                        "deadline": "Deadline to be confirmed",
                        "expected_outcome": "Enable precise risk quantification.",
                    }
                ],
                "unknowns": ["Specific financial, technical, and operational figures"],
                "needed": ["Detailed timeline and budget documentation"],
            })

        payload = {
            "executive_summary": (
                f"Evaluation identified {len(raw_risks)} primary risk vector(s). "
                f"Key threat domains: {', '.join([r['category'].value for r in raw_risks])}. "
                "Immediate governance actions should target critical solvency and operational deadlines."
            ),
            "identified_risks": raw_risks,
            "known_facts": known_facts,
            "unknown_aspects": list(dict.fromkeys(unknowns)),
            "needed_to_assess_accurately": list(dict.fromkeys(needed)),
            "follow_up_questions": [
                "What is your exact remaining cash runway in months?",
                "What percentage of overall revenue depends on the expiring contract?",
                "Do you have secondary backup vendors already qualified?",
                "What verified share of revenue depends on each key customer or contract?",
            ],
        }

        return self._post_process_findings(
            payload, situation, conversation_id, start_time,
            "Deterministic 5-Factor Scoring Matrix (Impact*0.35 + Prob*0.25 + Urgency*0.25 + Ev*0.15)",
            security_warnings, conflicts, rag_sources, use_crew_ai, extracted_facts, fact_validation
        )

    def _post_process_findings(
        self,
        data: Dict[str, Any],
        situation: str,
        conversation_id: str,
        start_time: float,
        methodology_label: str,
        security_warnings: List[str],
        conflicts: List[str],
        rag_sources: List[EvidenceSource],
        use_crew_ai: bool = False,
        extracted_facts: Optional[List[ExtractedFact]] = None,
        fact_validation: Optional[FactValidationResult] = None,
    ) -> RiskAnalysisResponse:
        """
        Guarantees deterministic calculation, source mapping, and anti-hallucination validation.
        """
        parsed_risks: List[IdentifiedRisk] = []
        all_actions: List[ActionableRecommendation] = []
        scores: List[float] = []
        report_warnings: List[str] = []
        extracted_fact_models = extracted_facts or FactExtractor.extract(
            "\n".join([situation] + [source.exact_quote for source in rag_sources])
        )
        fact_validation = fact_validation or FactValidator.validate(extracted_fact_models)
        report_warnings.extend(fact_validation.warnings)
        raw_findings = RiskDeduplicator.structure_risk_chain(data.get("identified_risks", []))

        # Safe category mapper
        def coerce_category(cat_val: Any) -> RiskTaxonomyCategory:
            if isinstance(cat_val, RiskTaxonomyCategory):
                return cat_val
            s_val = str(cat_val).lower().strip()
            for c in RiskTaxonomyCategory:
                if c.value.lower() in s_val or s_val in c.value.lower():
                    return c
            return RiskTaxonomyCategory.STRATEGIC

        for r_dict in raw_findings:
            category = coerce_category(r_dict.get("category", "Strategic Risk"))
            
            # Deterministic calculation using 5-factor scoring
            imp = float(r_dict.get("impact", r_dict.get("impact_rating", 3.5)))
            prob = float(r_dict.get("probability", r_dict.get("probability_rating", 3.5)))
            urg = float(r_dict.get("urgency", r_dict.get("urgency_rating", 3.5)))
            ev_q = float(r_dict.get("evidence_quality", 4.0))

            severity, numerical_score = RiskScoringMethodology.calculate_severity(imp, prob, urg, ev_q)
            scores.append(numerical_score)

            quotes = r_dict.get("exact_quotes", r_dict.get("quotes", r_dict.get("evidence", [])))
            if not isinstance(quotes, list):
                quotes = [str(quotes)]

            # Build traceable evidence sources.  Never attach every retrieved
            # document to every risk: each source must support this finding's
            # specific quote.
            sources: List[EvidenceSource] = []
            risk_warnings: List[str] = []
            for q in quotes:
                quote = str(q).strip()
                if RiskReportQualityGate.quote_is_supported(quote, situation):
                    matching_fact = next((fact for fact in extracted_fact_models if RiskReportQualityGate.quote_is_supported(quote, fact.source_text)), None)
                    sources.append(EvidenceSource(
                        source_type="User Input", exact_quote=quote,
                        fact_id=matching_fact.fact_id if matching_fact else None,
                    ))
                    continue
                matching_documents = [
                    source for source in rag_sources
                    if RiskReportQualityGate.quote_is_supported(quote, source.exact_quote)
                    or RiskReportQualityGate.quote_is_supported(source.exact_quote, quote)
                ]
                if matching_documents:
                    sources.extend(matching_documents)
                else:
                    risk_warnings.append("An unsupported evidence quote was excluded from this risk.")

            # Deduplicate identical citations while preserving distinct document locations.
            unique_sources: List[EvidenceSource] = []
            seen_sources = set()
            for source in sources:
                key = (source.source_type, source.document_name, source.page_number,
                       RiskReportQualityGate.normalise(source.exact_quote))
                if key not in seen_sources:
                    unique_sources.append(source)
                    seen_sources.add(key)
            sources = unique_sources
            sources = [
                source.model_copy(update={
                    "fact_id": source.fact_id or next(
                        (fact.fact_id for fact in extracted_fact_models
                         if RiskReportQualityGate.quote_is_supported(source.exact_quote, fact.source_text)
                         or RiskReportQualityGate.quote_is_supported(fact.source_text, source.exact_quote)),
                        None,
                    )
                })
                for source in sources
            ]
            if not sources:
                risk_warnings.append("Risk requires human review because no verifiable evidence citation remains.")

            # Calculate confidence score
            conf_score, conf_level = RiskScoringMethodology.calculate_confidence(
                evidence_count=len(sources),
                has_direct_source=bool(sources),
                missing_info_count=len(r_dict.get("unknowns", [])),
            )

            # Build actionable recommendations
            recs: List[ActionableRecommendation] = []
            for rec_index, rec_item in enumerate(r_dict.get("recommendations", r_dict.get("recommended_actions", []))):
                # Deterministic distribution: the lead action tracks severity;
                # follow-up actions step down one level.
                priority_order = [RiskSeverity.CRITICAL, RiskSeverity.HIGH, RiskSeverity.MEDIUM, RiskSeverity.LOW]
                severity_index = priority_order.index(severity)
                priority = priority_order[min(severity_index + rec_index, len(priority_order) - 1)]
                if isinstance(rec_item, dict):
                    owner = rec_item.get("owner", "Executive Team")
                    deadline = rec_item.get("deadline", "Deadline to be confirmed")
                    action_evidence = " ".join(source.exact_quote for source in sources).lower()
                    owner_validated = RiskReportQualityGate.normalise(owner) in action_evidence
                    deadline_validated = (
                        RiskReportQualityGate.normalise(deadline) in action_evidence
                        and "deadline to be confirmed" not in RiskReportQualityGate.normalise(deadline)
                    )
                    action_warnings = []
                    if not RiskReportQualityGate.owner_is_valid(owner):
                        action_warnings.append("Owner is generic or unvalidated; assign an accountable role.")
                    elif not owner_validated:
                        action_warnings.append("Owner is a proposed role, not an owner explicitly confirmed in the evidence.")
                        owner = "To be assigned"
                    if not deadline_validated:
                        action_warnings.append("Deadline is derived from priority and requires confirmation against the operating timeline.")
                    action_obj = ActionableRecommendation(
                        action=rec_item.get("action", str(rec_item)),
                        priority=priority,
                        owner=owner,
                        deadline=deadline,
                        expected_outcome=rec_item.get("expected_outcome", "Mitigate risk exposure."),
                        related_risk_category=category,
                        related_risk_title=r_dict.get("title", f"{category.value} Finding"),
                        owner_validated=owner_validated,
                        deadline_validated=deadline_validated,
                        validation_warnings=action_warnings,
                    )
                else:
                    action_obj = ActionableRecommendation(
                        action=str(rec_item),
                        priority=priority,
                        owner="Operations Team",
                        deadline="Deadline to be confirmed",
                        expected_outcome="Reduce operational bottleneck.",
                        related_risk_category=category,
                        related_risk_title=r_dict.get("title", f"{category.value} Finding"),
                        owner_validated=False,
                        deadline_validated=False,
                        validation_warnings=["Owner is generic or unvalidated; assign an accountable role."],
                    )
                recs.append(action_obj)
                all_actions.append(action_obj)

            # Missing breakdown for this risk
            miss_break = MissingInformationBreakdown(
                known_facts=[s.exact_quote for s in sources],
                unknown_aspects=RiskReportQualityGate.remove_known_items(
                    r_dict.get("unknowns", r_dict.get("unknown_aspects", [])),
                    [source.exact_quote for source in sources],
                ),
                needed_to_assess_accurately=RiskReportQualityGate.remove_known_items(
                    r_dict.get("needed", r_dict.get("needed_to_assess", [])),
                    [source.exact_quote for source in sources],
                ),
            )

            parsed_risks.append(IdentifiedRisk(
                category=category,
                severity=severity,
                numerical_score=numerical_score,
                confidence=conf_score,
                confidence_level=conf_level,
                impact_rating=imp,
                probability_rating=prob,
                urgency_rating=urg,
                evidence_quality_rating=ev_q,
                title=r_dict.get("title", f"{category.value} Finding"),
                description=r_dict.get("description", "Identified risk vector."),
                root_cause=r_dict.get("root_cause", "Input trigger"),
                contributing_factors=r_dict.get("contributing_factors", []),
                potential_impact=r_dict.get("potential_impact", "Business disruption."),
                sources=sources,
                evidence=[s.exact_quote for s in sources],
                evidence_fact_ids=[source.fact_id for source in sources if source.fact_id],
                recommended_actions=[r.action for r in recs],
                actionable_recommendations=recs,
                missing_information=miss_break.needed_to_assess_accurately,
                missing_breakdown=miss_break,
                quality_warnings=risk_warnings,
                score_rationale=[
                    f"Impact: {imp:.1f}/5.0; Probability: {prob:.1f}/5.0; Urgency: {urg:.1f}/5.0; Evidence quality: {ev_q:.1f}/5.0.",
                    f"Composite = ({imp:.1f} × 0.35) + ({prob:.1f} × 0.25) + ({urg:.1f} × 0.25) + ({ev_q:.1f} × 0.15) = {numerical_score:.2f}.",
                    f"Severity threshold applied deterministically: {severity.value}.",
                ],
            ))
            report_warnings.extend(risk_warnings)

        # Overall severity determined by highest numerical score
        if scores:
            max_score = max(scores)
            # The portfolio's overall level and displayed score use the same
            # deterministic worst-risk basis; this avoids a HIGH/CRITICAL label
            # paired with a diluted average score.
            avg_score = max_score
            if max_score >= 4.2:
                overall_risk = RiskSeverity.CRITICAL
            elif max_score >= 3.4:
                overall_risk = RiskSeverity.HIGH
            elif max_score >= 2.5:
                overall_risk = RiskSeverity.MEDIUM
            else:
                overall_risk = RiskSeverity.LOW
        else:
            overall_risk = RiskSeverity.MEDIUM
            avg_score = 2.5

        # Consolidate global missing information breakdown
        global_missing = MissingInformationBreakdown(
            known_facts=RiskReportQualityGate.unique([fact.source_text for fact in extracted_fact_models]),
            unknown_aspects=RiskReportQualityGate.remove_known_items(
                data.get("unknown_aspects", [u for r in parsed_risks for u in r.missing_breakdown.unknown_aspects if r.missing_breakdown]),
                [fact.source_text for fact in extracted_fact_models],
            ),
            needed_to_assess_accurately=RiskReportQualityGate.remove_known_items(
                data.get("needed_to_assess_accurately", [n for r in parsed_risks for n in r.missing_breakdown.needed_to_assess_accurately if r.missing_breakdown]),
                [fact.source_text for fact in extracted_fact_models],
            ),
        )

        severity_rank = {RiskSeverity.CRITICAL: 0, RiskSeverity.HIGH: 1, RiskSeverity.MEDIUM: 2, RiskSeverity.LOW: 3}
        all_actions.sort(key=lambda action: (severity_rank[action.priority], action.related_risk_category.value, action.action))
        follow_up_questions = RiskReportQualityGate.relevant_questions(
            data.get("follow_up_questions", []), global_missing.known_facts
        )
        dependencies: List[RiskDependency] = []
        cascade_rules = {
            RiskTaxonomyCategory.SUPPLIER: (RiskTaxonomyCategory.OPERATIONAL, "may_cascade_to"),
            RiskTaxonomyCategory.TECHNOLOGY: (RiskTaxonomyCategory.OPERATIONAL, "may_cascade_to"),
            RiskTaxonomyCategory.CUSTOMER: (RiskTaxonomyCategory.FINANCIAL, "contributes_to"),
            RiskTaxonomyCategory.HR: (RiskTaxonomyCategory.OPERATIONAL, "may_cascade_to"),
            RiskTaxonomyCategory.CYBERSECURITY: (RiskTaxonomyCategory.LEGAL_COMPLIANCE, "may_cascade_to"),
        }
        for source_risk in parsed_risks:
            target_rule = cascade_rules.get(source_risk.category)
            if not target_rule:
                continue
            target_category, relationship = target_rule
            for target_risk in parsed_risks:
                if target_risk.category != target_category or target_risk.title == source_risk.title:
                    continue
                shared_evidence = sorted(set(source_risk.evidence) & set(target_risk.evidence))
                if shared_evidence:
                    dependencies.append(RiskDependency(
                        source_risk_title=source_risk.title,
                        target_risk_title=target_risk.title,
                        relationship=relationship,
                        evidence=shared_evidence,
                        confidence=ConfidenceLevel.MEDIUM,
                    ))

        validation_result = RiskReportQualityGate.output_warnings(
            parsed_risks, all_actions, extracted_fact_models, fact_validation.important_fact_ids
        )
        report_warnings.extend(validation_result["warnings"])
        if validation_result["coverage"] < validation_result["minimum_coverage"]:
            report_warnings.extend(
                f"Uncovered fact: {fact}" for fact in validation_result["uncovered"]
            )

        exec_time = round(time.time() - start_time, 3)

        return RiskAnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            overall_risk=overall_risk,
            overall_score=avg_score,
            executive_summary=data.get("executive_summary", "Comprehensive risk assessment completed."),
            identified_risks=parsed_risks,
            priority_actions=all_actions[:6],
            missing_information=global_missing.needed_to_assess_accurately,
            missing_breakdown=global_missing,
            conflicts_detected=conflicts,
            security_warnings=security_warnings,
            follow_up_questions=follow_up_questions,
            known_facts=global_missing.known_facts,
            inferences=data.get("inferences", [r.description for r in parsed_risks]),
            analysis_methodology=methodology_label,
            execution_time_seconds=exec_time,
            used_agents=use_crew_ai,
            quality_warnings=RiskReportQualityGate.unique(report_warnings),
            risk_dependencies=dependencies,
            report_validation=ReportValidation(
                passed=not validation_result["warnings"] and not report_warnings,
                status=("VALID" if not validation_result["warnings"] and not report_warnings else "REANALYSIS_REQUIRED"),
                valid_for_distribution=not validation_result["warnings"] and not report_warnings,
                checks_performed=[
                    "verbatim evidence validation", "duplicate-risk consolidation", "risk-to-action mapping",
                    "fact-to-risk coverage", "priority ranking", "known-vs-unknown reconciliation",
                    "contradiction detection", "cross-risk dependency analysis",
                ],
                fact_to_risk_coverage=validation_result["coverage"],
                important_fact_count=validation_result["important_fact_count"],
                important_facts_linked_to_risks=validation_result["linked_important_fact_count"],
                unlinked_important_fact_ids=validation_result["unlinked_important_fact_ids"],
                risks_without_evidence=validation_result["no_evidence"],
                risks_without_fact_id=validation_result["no_fact_id"],
                risks_with_invalid_fact_id=validation_result["invalid_fact_ids"],
                risks_with_unverifiable_citation=validation_result["unverifiable_citations"],
                risks_without_actions=validation_result["no_actions"],
                actions_without_specific_mapping=validation_result["unmapped_actions"],
                warnings=RiskReportQualityGate.unique(report_warnings),
            ),
            extracted_facts=[ExtractedFactSchema(
                fact_id=fact.fact_id, category=fact.category, metric=fact.metric,
                value=fact.value, unit=fact.unit, scope=fact.scope, timeframe=fact.timeframe,
                certainty=fact.certainty, source_text=fact.source_text,
            ) for fact in extracted_fact_models],
        )


# Global Service Singleton
risk_analyzer_service = AIRiskAnalyzerService()
