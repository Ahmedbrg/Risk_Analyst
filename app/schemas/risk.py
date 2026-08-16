"""
AI Risk Analyst — Enterprise Pydantic Schemas for Structured Risk Assessment.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskTaxonomyCategory(str, Enum):
    """
    Fixed 10-Domain Enterprise Risk Taxonomy (ISO 31000 & COSO aligned).
    """
    FINANCIAL = "Financial Risk"
    OPERATIONAL = "Operational Risk"
    CYBERSECURITY = "Cybersecurity Risk"
    LEGAL_COMPLIANCE = "Legal / Compliance Risk"
    SUPPLIER = "Supplier Risk"
    CUSTOMER = "Customer Risk"
    STRATEGIC = "Strategic Risk"
    HR = "HR / Workforce Risk"
    REPUTATIONAL = "Reputational Risk"
    TECHNOLOGY = "Technology Risk"


# Compatibility alias
RiskCategory = RiskTaxonomyCategory


class EvidenceSource(BaseModel):
    """Traceable citation to exact user text or document page/section."""
    source_type: str = Field("User Input", description="'User Input' or 'Document'")
    document_name: Optional[str] = Field(None, description="Filename if from document")
    page_number: Optional[int] = Field(None, description="Page number if applicable")
    section: Optional[str] = Field(None, description="Section heading if found")
    paragraph_number: Optional[int] = Field(None, description="Paragraph index within the source section")
    exact_quote: str = Field(..., description="Exact verifiable text quote")
    fact_id: Optional[str] = Field(None, description="Identifier of the extracted explicit fact")
    certainty: str = Field("explicit", description="Evidence certainty; only explicit facts may support a finding")


class ExtractedFactSchema(BaseModel):
    fact_id: str
    category: str
    metric: str
    value: Optional[float] = None
    unit: Optional[str] = None
    scope: Optional[str] = None
    timeframe: Optional[str] = None
    certainty: str
    source_text: str


class ActionableRecommendation(BaseModel):
    """Concrete, prioritized decision-support mitigation."""
    action: str = Field(..., description="Action description")
    priority: RiskSeverity = Field(..., description="Urgency priority")
    owner: str = Field("Executive Team", description="Assigned role e.g. CFO, Legal, Procurement")
    deadline: str = Field("Immediate", description="Action timeframe e.g. 7 days, 14 days")
    expected_outcome: str = Field(..., description="Measurable business objective")
    related_risk_category: RiskTaxonomyCategory = Field(..., description="Risk domain addressed")
    related_risk_title: Optional[str] = Field(None, description="Specific risk finding addressed by this action")
    owner_validated: bool = Field(False, description="Whether the owner role was explicitly provided in evidence")
    deadline_validated: bool = Field(False, description="Whether the deadline was explicitly provided in evidence")
    validation_warnings: List[str] = Field(default_factory=list, description="Deterministic action-quality warnings")


# Compatibility alias
PriorityAction = ActionableRecommendation


class MissingInformationBreakdown(BaseModel):
    """Anti-hallucination triad: separates verified facts from unknown elements."""
    known_facts: List[str] = Field(default_factory=list, description="Explicit statements provided by user/documents")
    unknown_aspects: List[str] = Field(default_factory=list, description="Uncertainties or unverified assumptions")
    needed_to_assess_accurately: List[str] = Field(default_factory=list, description="Exact data points required for 100% confidence")


class IdentifiedRisk(BaseModel):
    """Structured, evidence-grounded risk finding."""
    category: RiskTaxonomyCategory
    severity: RiskSeverity
    numerical_score: float = Field(..., ge=1.0, le=5.0, description="Explainable composite score (1.0 to 5.0)")
    impact_rating: float = Field(..., ge=1.0, le=5.0)
    probability_rating: float = Field(..., ge=1.0, le=5.0)
    urgency_rating: float = Field(..., ge=1.0, le=5.0)
    evidence_quality_rating: float = Field(..., ge=1.0, le=5.0)
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    confidence_level: ConfidenceLevel = Field(ConfidenceLevel.HIGH, description="Confidence rating")
    title: str
    description: str
    root_cause: str = Field("Identified threat vector", description="Primary origin of the risk")
    contributing_factors: List[str] = Field(default_factory=list, description="Secondary symptoms or chain events")
    potential_impact: str
    sources: List[EvidenceSource] = Field(default_factory=list, description="Traceable grounding citations")
    evidence: List[str] = Field(default_factory=list, description="Flat list of quote strings for backward compatibility")
    recommended_actions: List[str] = Field(default_factory=list, description="Action strings for backward compatibility")
    actionable_recommendations: List[ActionableRecommendation] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    missing_breakdown: Optional[MissingInformationBreakdown] = None
    quality_warnings: List[str] = Field(default_factory=list, description="Grounding and completeness checks requiring review")
    score_rationale: List[str] = Field(default_factory=list, description="Deterministic explanation of each score component")
    evidence_fact_ids: List[str] = Field(default_factory=list)


class RiskDependency(BaseModel):
    """Evidence-based relationship between two separately reported risks."""
    source_risk_title: str
    target_risk_title: str
    relationship: str = Field(..., description="contributes_to, may_cascade_to, or shares_driver_with")
    evidence: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class ReportValidation(BaseModel):
    """Final deterministic validation status; warnings require human review."""
    passed: bool
    status: str = Field("REANALYSIS_REQUIRED", description="VALID only when every final QC check passes")
    valid_for_distribution: bool = Field(False, description="Whether PDF/export delivery is permitted")
    checks_performed: List[str] = Field(default_factory=list)
    fact_to_risk_coverage: float = Field(0.0, ge=0.0, le=1.0)
    important_fact_count: int = Field(0, ge=0)
    important_facts_linked_to_risks: int = Field(0, ge=0)
    unlinked_important_fact_ids: List[str] = Field(default_factory=list)
    risks_without_evidence: List[str] = Field(default_factory=list)
    risks_without_fact_id: List[str] = Field(default_factory=list)
    risks_with_invalid_fact_id: List[str] = Field(default_factory=list)
    risks_with_unverifiable_citation: List[str] = Field(default_factory=list)
    risks_without_actions: List[str] = Field(default_factory=list)
    actions_without_specific_mapping: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RiskAnalysisRequest(BaseModel):
    situation: str = Field(..., min_length=1, description="Natural language description or prompt")
    conversation_id: Optional[str] = None
    include_rag: bool = False
    use_crew_ai: bool = False
    document_ids: Optional[List[str]] = None


class RiskAnalysisResponse(BaseModel):
    analysis_id: str
    conversation_id: str
    overall_risk: RiskSeverity
    overall_score: float = Field(3.5, description="Aggregated 1-5 severity score")
    executive_summary: str
    identified_risks: List[IdentifiedRisk]
    priority_actions: List[ActionableRecommendation]
    missing_information: List[str]
    missing_breakdown: Optional[MissingInformationBreakdown] = None
    conflicts_detected: List[str] = Field(default_factory=list, description="Factual or numerical contradictions flagged")
    security_warnings: List[str] = Field(default_factory=list, description="PII masking or injection alerts")
    follow_up_questions: List[str] = Field(default_factory=list)
    known_facts: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    analysis_methodology: str = "Deterministic Multi-Factor Scoring (Impact*0.35 + Prob*0.25 + Urgency*0.25 + Evidence*0.15)"
    execution_time_seconds: float
    used_agents: bool = False
    quality_warnings: List[str] = Field(default_factory=list, description="Report-level quality-control findings")
    risk_dependencies: List[RiskDependency] = Field(default_factory=list)
    report_validation: Optional[ReportValidation] = None
    extracted_facts: List[ExtractedFactSchema] = Field(default_factory=list)
