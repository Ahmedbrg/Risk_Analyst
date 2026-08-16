"""Validation and materiality classification for extracted facts."""

from dataclasses import dataclass
from typing import Iterable, List

from app.core.facts import ExtractedFact


@dataclass(frozen=True)
class FactValidationResult:
    """Facts eligible for risk-coverage measurement and validation findings."""

    important_fact_ids: List[str]
    invalid_fact_ids: List[str]
    warnings: List[str]


class FactValidator:
    """Keeps fact validation separate from risk detection.

    A fact is important when it has an explicit non-general business domain or
    a recognised metric.  This is a deterministic materiality rule, not a
    risk inference: validation never creates a risk to improve coverage.
    """

    @classmethod
    def validate(cls, facts: Iterable[ExtractedFact]) -> FactValidationResult:
        important_fact_ids: List[str] = []
        invalid_fact_ids: List[str] = []
        for fact in facts:
            if not fact.fact_id or not fact.source_text.strip() or fact.certainty != "explicit":
                invalid_fact_ids.append(fact.fact_id)
                continue
            if fact.category != "General" or fact.metric != "statement":
                important_fact_ids.append(fact.fact_id)

        warnings = []
        if invalid_fact_ids:
            warnings.append("One or more extracted facts failed explicit-source validation.")
        return FactValidationResult(
            important_fact_ids=important_fact_ids,
            invalid_fact_ids=invalid_fact_ids,
            warnings=warnings,
        )
