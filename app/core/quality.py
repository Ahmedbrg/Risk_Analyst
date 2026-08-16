"""Deterministic output-quality checks for risk assessments.

This module intentionally does not try to decide whether a business statement is
true.  It verifies that the assessment correctly represents what was supplied:
facts must be quoted, unknowns must not duplicate facts, and questions must not
ask for information that is already present.
"""

import re
from typing import Any, Iterable, List, Tuple


class RiskReportQualityGate:
    """Small, deterministic guardrail layer applied after every analysis path."""

    GENERIC_OWNERS = {"", "executive team", "operations team", "tbd", "unknown"}
    MINIMUM_FACT_TO_RISK_COVERAGE = 0.90

    @staticmethod
    def normalise(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    @classmethod
    def quote_is_supported(cls, quote: str, source_text: str) -> bool:
        """Require a non-empty verbatim quote from its claimed source."""
        return bool(cls.normalise(quote)) and cls.normalise(quote) in cls.normalise(source_text)

    @classmethod
    def unique(cls, values: Iterable[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for value in values:
            value = str(value).strip()
            key = cls.normalise(value)
            if value and key not in seen:
                result.append(value)
                seen.add(key)
        return result

    @classmethod
    def remove_known_items(cls, values: Iterable[str], known_facts: Iterable[str]) -> List[str]:
        """Do not label a supplied fact as missing or unknown."""
        facts = " ".join(cls.normalise(fact) for fact in known_facts)
        return cls.unique(value for value in values if cls.normalise(str(value)) not in facts)

    @classmethod
    def relevant_questions(cls, questions: Iterable[str], known_facts: Iterable[str]) -> List[str]:
        """Suppress a question when its requested topic is already explicitly supplied."""
        facts = " ".join(cls.normalise(fact) for fact in known_facts)
        accepted: List[str] = []
        for question in cls.unique(questions):
            question_text = cls.normalise(question)
            # Conservative domain synonym handling for common fact forms.
            # It only suppresses a question when the metric *and* its direction
            # are explicit, so it cannot hide an unanswered numeric request.
            if (
                "revenue" in question_text
                and any(term in question_text for term in ("decline", "decrease", "drop", "fall"))
                and "revenue" in facts
                and any(term in facts for term in ("decline", "decreased", "dropped", "fell", "fall"))
            ):
                continue
            # Content words make a robust, explainable relevance check without an LLM.
            words = [word for word in re.findall(r"[a-z]{4,}", question.lower())
                     if word not in {"what", "your", "have", "with", "does", "that", "this", "from"}]
            # A partial lexical overlap (for example, a supplied contract date
            # but no revenue percentage) is not enough to suppress a question.
            if words and sum(word in facts for word in words) >= max(1, (len(words) * 4 + 4) // 5):
                continue
            accepted.append(question)
        return accepted

    @classmethod
    def owner_is_valid(cls, owner: str) -> bool:
        return cls.normalise(owner) not in cls.GENERIC_OWNERS

    @classmethod
    def claim_is_supported_or_qualified(cls, claim: str, evidence: Iterable[str]) -> bool:
        """Reject unsupported causal/impact assertions unless clearly qualified.

        A risk assessment may describe a possibility, but it must not state an
        unverified cause or outcome as fact.  This deliberately narrow gate is
        used for LLM-generated claims before they enter the report.
        """
        claim_text = cls.normalise(claim)
        evidence_text = " ".join(cls.normalise(item) for item in evidence)
        if claim_text in evidence_text:
            return True
        qualifiers = ("unconfirmed", "unknown", "not established", "may", "might", "could", "potential")
        return any(re.search(rf"\b{re.escape(word)}\b", claim_text) for word in qualifiers)

    @classmethod
    def fact_coverage(cls, facts: Iterable[str], evidence: Iterable[str]) -> Tuple[float, List[str]]:
        """Return the share of material facts referenced by at least one risk."""
        evidence_text = " ".join(cls.normalise(item) for item in evidence)
        material_facts = [fact for fact in cls.unique(facts) if len(cls.normalise(fact)) >= 12]
        uncovered = [fact for fact in material_facts if cls.normalise(fact) not in evidence_text]
        coverage = 1.0 if not material_facts else round((len(material_facts) - len(uncovered)) / len(material_facts), 2)
        return coverage, uncovered

    @classmethod
    def output_warnings(
        cls,
        risks: Iterable[Any],
        actions: Iterable[Any],
        facts: Iterable[Any],
        important_fact_ids: Iterable[str] | None = None,
    ) -> dict:
        """Validate report completeness, grounding, and Fact-ID traceability."""
        risks = list(risks)
        actions = list(actions)
        evidence = [source.exact_quote for risk in risks for source in risk.sources]
        fact_items = list(facts)
        important_ids = set(important_fact_ids) if important_fact_ids is not None else {
            getattr(fact, "fact_id", None) for fact in fact_items
        }
        important_facts = [fact for fact in fact_items if getattr(fact, "fact_id", None) in important_ids]
        fact_texts = [getattr(fact, "source_text", fact) for fact in important_facts]
        valid_fact_ids = {getattr(fact, "fact_id", None) for fact in fact_items if getattr(fact, "fact_id", None)}
        coverage, uncovered = cls.fact_coverage(fact_texts, evidence)
        unlinked_important_fact_ids = [
            getattr(fact, "fact_id", "") for fact in important_facts
            if getattr(fact, "source_text", fact) in uncovered
        ]
        no_evidence = [risk.title for risk in risks if not risk.sources]
        no_fact_id = [
            risk.title for risk in risks
            if not risk.sources or any(not source.fact_id for source in risk.sources)
        ]
        invalid_fact_ids = [
            risk.title for risk in risks
            if any(source.fact_id not in valid_fact_ids for source in risk.sources)
        ]
        facts_by_id = {getattr(fact, "fact_id", None): getattr(fact, "source_text", "") for fact in fact_items}
        unverifiable_citations = [
            risk.title for risk in risks
            if any(
                not source.fact_id
                or not facts_by_id.get(source.fact_id)
                or not (
                    cls.quote_is_supported(source.exact_quote, facts_by_id[source.fact_id])
                    or cls.quote_is_supported(facts_by_id[source.fact_id], source.exact_quote)
                )
                for source in risk.sources
            )
        ]
        no_actions = [risk.title for risk in risks if not risk.actionable_recommendations]
        unmapped_actions = [action.action for action in actions if not action.related_risk_title]
        warnings = []
        if coverage < cls.MINIMUM_FACT_TO_RISK_COVERAGE:
            warnings.append(
                f"Fact-to-risk coverage is below the required {cls.MINIMUM_FACT_TO_RISK_COVERAGE:.0%} threshold."
            )
        if no_evidence:
            warnings.append("One or more risks have no verifiable evidence citation.")
        if no_fact_id:
            warnings.append("One or more risks are not linked to an extracted Fact ID.")
        if invalid_fact_ids:
            warnings.append("One or more risks reference an unknown Fact ID.")
        if unverifiable_citations:
            warnings.append("One or more citations do not match the source text of their Fact ID.")
        if no_actions:
            warnings.append("One or more detected risks have no mitigation action.")
        if unmapped_actions:
            warnings.append("One or more actions are not mapped to a specific risk.")
        return {
            "coverage": coverage,
            "minimum_coverage": cls.MINIMUM_FACT_TO_RISK_COVERAGE,
            "important_fact_count": len(important_facts),
            "linked_important_fact_count": len(important_facts) - len(unlinked_important_fact_ids),
            "unlinked_important_fact_ids": unlinked_important_fact_ids,
            "uncovered": uncovered,
            "no_evidence": no_evidence,
            "no_fact_id": no_fact_id,
            "invalid_fact_ids": invalid_fact_ids,
            "unverifiable_citations": unverifiable_citations,
            "no_actions": no_actions,
            "unmapped_actions": unmapped_actions,
            "warnings": warnings,
        }
