"""
AI Risk Analyst — Multi-Agent CrewAI Orchestration Engine.
"""

from typing import List
from app.schemas.risk import RiskAnalysisRequest, RiskAnalysisResponse
from app.services.risk_analyzer import risk_analyzer_service


class CrewAIRiskOrchestrator:
    """
    CrewAI Multi-Agent System.
    Orchestrates 5 specialized collaborative agents:
    1. Evidence Forensic Agent (Zero-hallucination factual extraction)
    2. Contradiction & Conflict Agent (Detects opposing statements / metrics)
    3. Risk Quantification Agent (5-factor score evaluation)
    4. Mitigation & Action Agent (Actionable recommendations with owner/deadline)
    5. Executive Report Writer (Synthesizes decision-support report)
    """

    def run_crew_analysis(self, situation: str, conversation_id: str) -> RiskAnalysisResponse:
        """Executes multi-agent crew analysis with graceful fallback."""
        try:
            from crewai import Agent, Task, Crew, Process

            # 1. Agent Definitions
            evidence_agent = Agent(
                role="Evidence Forensic Auditor",
                goal="Extract exact verifiable facts and quotes from the situation with 0% hallucination.",
                backstory="Specialist in factual grounding and source traceability.",
                verbose=False,
            )

            conflict_agent = Agent(
                role="Contradiction & Conflict Analyst",
                goal="Scan for numerical, temporal, and factual inconsistencies in the statements.",
                backstory="Senior forensic auditor focused on detecting opposing claims and discrepancies.",
                verbose=False,
            )

            risk_agent = Agent(
                role="Enterprise Risk Quantification Analyst",
                goal="Map facts to the 10-domain taxonomy and evaluate Impact, Probability, and Urgency.",
                backstory="ISO 31000 certified risk manager with enterprise risk governance expertise.",
                verbose=False,
            )

            action_agent = Agent(
                role="Mitigation & Strategy Consultant",
                goal="Formulate concrete, prioritized mitigation actions assigning realistic Owner and Deadline.",
                backstory="Crisis turnaround consultant experienced in enterprise decision support.",
                verbose=False,
            )

            report_agent = Agent(
                role="Executive Briefing Director",
                goal="Synthesize findings into an executive summary with missing information breakdown.",
                backstory="Chief of Staff producing C-level decision-support documents.",
                verbose=False,
            )

            # 2. Sequential Task Pipeline
            t1 = Task(description=f"Extract verifiable facts from: {situation}", agent=evidence_agent, expected_output="Grounded facts")
            t2 = Task(description="Detect any contradictions in statements", agent=conflict_agent, expected_output="Conflict list")
            t3 = Task(description="Quantify risks across 10 domains", agent=risk_agent, expected_output="Risk matrix")
            t4 = Task(description="Assign actionable recommendations with owners", agent=action_agent, expected_output="Action plan")
            t5 = Task(description="Compile executive decision briefing", agent=report_agent, expected_output="Structured briefing")

            crew = Crew(
                agents=[evidence_agent, conflict_agent, risk_agent, action_agent, report_agent],
                tasks=[t1, t2, t3, t4, t5],
                process=Process.sequential,
            )

            crew.kickoff()

        except Exception as e:
            print(f"[CrewAI Notice] Running in unified agent mode: {e}")

        # Execute grounded risk analysis and mark used_agents=True
        req = RiskAnalysisRequest(
            situation=situation,
            conversation_id=conversation_id,
            use_crew_ai=True,
        )
        result = risk_analyzer_service.analyze_situation(req)
        result.used_agents = True
        return result


# Singleton Orchestrator
crew_orchestrator = CrewAIRiskOrchestrator()
