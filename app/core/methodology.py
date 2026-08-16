"""
AI Risk Analyst — Deterministic Scoring Engine, Conflict Detection, and Chain Deduplication.
"""

import re
from typing import List, Dict, Any, Tuple
from app.schemas.risk import EvidenceSource, RiskSeverity, ConfidenceLevel, RiskTaxonomyCategory


class RiskScoringMethodology:
    """
    Deterministic & Explainable Multi-Factor Risk Assessment Framework.

    Formula:
      Composite Score (S) = (Impact * 0.35) + (Probability * 0.25) + (Urgency * 0.25) + (Evidence_Weight * 0.15)
      Each factor is evaluated on a strict 1.0 to 5.0 scale.

    Thresholds:
      - 4.2 <= S <= 5.0 => CRITICAL
      - 3.4 <= S < 4.2  => HIGH
      - 2.5 <= S < 3.4  => MEDIUM
      - 1.0 <= S < 2.5  => LOW
    """

    @staticmethod
    def calculate_severity(
        impact: float,       # 1 (Negligible) to 5 (Catastrophic)
        probability: float,  # 1 (Rare < 10%) to 5 (Almost Certain > 90%)
        urgency: float,      # 1 (> 6 months) to 5 (Immediate < 14 days)
        evidence_quality: float, # 1 (Vague rumor) to 5 (Direct document / explicit metric)
    ) -> Tuple[RiskSeverity, float]:
        # Clamp inputs between 1.0 and 5.0
        imp = max(1.0, min(5.0, impact))
        prob = max(1.0, min(5.0, probability))
        urg = max(1.0, min(5.0, urgency))
        ev = max(1.0, min(5.0, evidence_quality))

        composite_score = (imp * 0.35) + (prob * 0.25) + (urg * 0.25) + (ev * 0.15)
        composite_score = round(composite_score, 2)

        if composite_score >= 4.2:
            return RiskSeverity.CRITICAL, composite_score
        elif composite_score >= 3.4:
            return RiskSeverity.HIGH, composite_score
        elif composite_score >= 2.5:
            return RiskSeverity.MEDIUM, composite_score
        else:
            return RiskSeverity.LOW, composite_score

    @staticmethod
    def calculate_confidence(
        evidence_count: int,
        has_direct_source: bool,
        missing_info_count: int,
    ) -> Tuple[float, ConfidenceLevel]:
        """
        Calculates numerical confidence (0.0 to 1.0) and qualitative level (HIGH, MEDIUM, LOW).
        """
        # A verbatim user/document citation is stronger than a model inference.
        # Unknowns reduce certainty about the assessment, not the fact itself.
        base = 0.45
        evidence_boost = min(0.30, evidence_count * 0.20)
        source_boost = 0.25 if has_direct_source else 0.0
        missing_penalty = min(0.25, missing_info_count * 0.05)

        score = base + evidence_boost + source_boost - missing_penalty
        score = round(max(0.10, min(0.99, score)), 2)

        if score >= 0.85:
            level = ConfidenceLevel.HIGH
        elif score >= 0.60:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return score, level


class ConflictDetector:
    """
    Detects factual and numerical contradictions within user statements or ingested documents.
    """

    @classmethod
    def detect_conflicts(cls, text: str, context: str = "") -> List[str]:
        combined = (context + " " + text).lower()
        conflicts: List[str] = []

        # 1. Cash runway / reserves contradiction
        runway_matches = re.findall(r"(\d+)\s*(?:months?|mths?)\s*(?:of\s*)?(?:cash|runway|reserves)", combined)
        if len(set(runway_matches)) > 1:
            conflicts.append(
                f"Conflicting Information: Cash runway stated inconsistently as {', '.join(set(runway_matches))} months."
            )

        # 2. Revenue direction contradiction (e.g. 'revenue increased' AND 'revenue decreased')
        has_rev_increase = any(w in combined for w in ["revenue increased", "growth of", "profit increased", "revenue grew"])
        has_rev_decrease = any(w in combined for w in ["revenue decreased", "revenue dropped", "revenue fell", "revenue decline"])
        if has_rev_increase and has_rev_decrease:
            conflicts.append(
                "Conflicting Information: Contradictory statements detected regarding revenue (both growth and decline mentioned)."
            )

        # 3. Financial values only conflict when they describe the *same*
        # metric.  A total debt, a debt maturity, and a contract value are
        # different facts and must never be compared as contradictory figures.
        metric_values: Dict[str, List[str]] = {}
        for sentence in re.split(r"(?<=[.!?;])\s+|\n+", combined):
            values = re.findall(r"(?:€|\$|eur|usd)\s*(\d+(?:\.\d+)?(?:\s*(?:m|k|million|thousand))?)", sentence)
            if not values:
                continue
            if "debt" in sentence and any(word in sentence for word in ["due", "matur", "repay"]):
                metric = "debt maturity"
            elif "debt" in sentence:
                metric = "outstanding debt"
            elif any(word in sentence for word in ["contract", "agreement"]):
                metric = "contract value"
            elif "revenue" in sentence or "turnover" in sentence:
                metric = "revenue"
            else:
                continue
            metric_values.setdefault(metric, []).extend(values)
        for metric, values in metric_values.items():
            if len(set(values)) > 2:
                displayed_figures = sorted(set(values))[:3]
                conflicts.append(
                    f"Numerical Discrepancy: {metric.title()} values differ ({', '.join(displayed_figures)}). No value was selected."
                )

        return conflicts

    @classmethod
    def detect_document_conflicts(cls, sources: List[EvidenceSource]) -> List[str]:
        """Flag incompatible revenue values from distinct documents; never choose one."""
        observations: Dict[str, List[str]] = {}
        for source in sources:
            if source.source_type != "Document":
                continue
            values = re.findall(
                r"(?:revenue|turnover)[^€$\n]{0,40}(?:€|\$)\s*(\d+(?:\.\d+)?\s*(?:m|k|million|thousand)?)",
                source.exact_quote,
                re.IGNORECASE,
            )
            label = f"{source.document_name or 'Document'} p.{source.page_number or '?'}"
            for value in values:
                observations.setdefault("revenue", []).append(f"{label}: {value.strip()}")

        conflicts = []
        for metric, values in observations.items():
            distinct_values = {value.rsplit(": ", 1)[-1] for value in values}
            if len(distinct_values) > 1:
                conflicts.append(
                    f"Document conflict: {metric.title()} values disagree ({'; '.join(values)}). No value was selected."
                )
        return conflicts


class RiskDeduplicator:
    """
    Consolidates cascading risks into root causes, contributing factors, and consequences
    to prevent risk duplication and artificial score inflation.
    """

    @classmethod
    def structure_risk_chain(cls, risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Map related categories (Financial + Supplier + Contractual often form a single solvency chain)
        by_category: Dict[Any, Dict[str, Any]] = {}

        for r in risks:
            cat = r.get("category")
            # A category is not itself a duplicate.  Callers may supply an
            # explicit key when one domain contains independent vectors (for
            # example customer churn and customer concentration).
            key = r.get("dedupe_key", cat)
            if key not in by_category:
                by_category[key] = r.copy()
                continue
            root = by_category[key]
            root.setdefault("contributing_factors", []).extend(
                [r.get("title", "")] + r.get("contributing_factors", [])
            )
            if r.get("potential_impact"):
                root.setdefault("consequences", []).append(r["potential_impact"])
            root["contributing_factors"] = list(dict.fromkeys(filter(None, root["contributing_factors"])))

        return list(by_category.values())
