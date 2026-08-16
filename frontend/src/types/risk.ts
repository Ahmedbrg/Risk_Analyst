export type RiskSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface IdentifiedRisk {
  category: string;
  severity: RiskSeverity;
  confidence: number;
  title: string;
  description: string;
  potential_impact: string;
  evidence: string[];
  recommended_actions: string[];
  missing_information: string[];
  score_rationale: string[];
  quality_warnings: string[];
}

export interface PriorityAction {
  action: string;
  priority: RiskSeverity;
  owner: string;
  deadline: string;
  expected_outcome: string;
  related_risk_category: string;
  related_risk_title?: string;
  validation_warnings: string[];
}

export interface RiskDependency {
  source_risk_title: string;
  target_risk_title: string;
  relationship: string;
  evidence: string[];
  confidence: "LOW" | "MEDIUM" | "HIGH";
}

export interface ReportValidation {
  passed: boolean;
  status: "VALID" | "REANALYSIS_REQUIRED";
  valid_for_distribution: boolean;
  fact_to_risk_coverage: number;
  risks_without_fact_id: string[];
  risks_with_invalid_fact_id: string[];
  risks_with_unverifiable_citation: string[];
  warnings: string[];
}

export interface RiskAnalysisResponse {
  analysis_id: string;
  conversation_id: string;
  overall_risk: RiskSeverity;
  overall_score: number;
  executive_summary: string;
  identified_risks: IdentifiedRisk[];
  priority_actions: PriorityAction[];
  missing_information: string[];
  follow_up_questions: string[];
  known_facts: string[];
  inferences: string[];
  analysis_methodology: string;
  execution_time_seconds: number;
  used_agents: boolean;
  quality_warnings: string[];
  risk_dependencies: RiskDependency[];
  report_validation?: ReportValidation;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  risk_analysis?: RiskAnalysisResponse;
}
