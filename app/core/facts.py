"""Deterministic fact extraction used as the evidence boundary for risk analysis."""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ExtractedFact:
    fact_id: str
    category: str
    metric: str
    value: Optional[float]
    unit: Optional[str]
    scope: Optional[str]
    timeframe: Optional[str]
    certainty: str
    source_text: str


class FactExtractor:
    """Extract explicit business facts; it never infers a fact from a risk."""

    METRIC_RULES = (
        ("revenue_decline", "Financial", ("revenue", "declin")),
        ("revenue_decline", "Financial", ("revenue", "drop")),
        ("revenue_decline", "Financial", ("revenue", "fell")),
        ("revenue_concentration", "Customer", ("top", "customer", "client", "revenue")),
        ("customer_demand_reduction", "Customer", ("customer", "client", "reduce", "purchases")),
        ("contract_expiration", "Legal", ("contract", "agreement", "expire")),
        ("cash_reserve", "Financial", ("cash", "reserve")),
        ("cash_runway", "Financial", ("cash", "runway")),
        ("debt_maturity", "Financial", ("debt", "due")),
        ("outstanding_debt", "Financial", ("debt",)),
        ("margin_decline", "Financial", ("margin", "decline")),
        ("cost_increase", "Financial", ("cost", "increase")),
        ("supplier_dependency", "Supplier", ("sole", "supplier")),
        ("supplier_delivery", "Supplier", ("supplier", "delay")),
        ("supplier_delivery", "Supplier", ("supplier", "late")),
        ("inventory_coverage", "Operational", ("inventory",)),
        ("backup_supplier_capacity", "Supplier", ("second", "supplier", "capacity")),
        ("patch_management", "Cybersecurity", ("patch",)),
        ("outdated_devices", "Cybersecurity", ("device", "outdated")),
        ("internet_facing_exposure", "Cybersecurity", ("internet-facing", "server")),
        ("security_incident", "Cybersecurity", ("security", "incident")),
        ("cost_reduction", "Operational", ("cost", "reduction")),
    )

    @classmethod
    def extract(cls, text: str) -> List[ExtractedFact]:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?;])\s+|\n+", text) if len(part.strip()) > 3]
        facts: List[ExtractedFact] = []
        seen = set()
        for sentence in sentences:
            lower = sentence.lower()
            if "[redacted_adversarial_instruction]" in lower:
                continue
            metric, category = cls._classify(lower)
            # Keep every explicit statement as a fact, including statements
            # without a recognised metric, so coverage validation is honest.
            value, unit = cls._extract_value(lower)
            key = (metric, lower)
            if key in seen:
                continue
            seen.add(key)
            facts.append(ExtractedFact(
                fact_id=f"F-{len(facts) + 1:03d}", category=category, metric=metric,
                value=value, unit=unit, scope=cls._scope(lower), timeframe=cls._timeframe(lower),
                certainty="explicit", source_text=sentence,
            ))
        return facts

    @classmethod
    def _classify(cls, text: str) -> tuple[str, str]:
        if ("customer" in text or "client" in text) and "revenue" in text:
            if any(term in text for term in ("top", "largest", "one customer", "one client", "represents")):
                return "revenue_concentration", "Customer"
        for metric, category, terms in cls.METRIC_RULES:
            # Stem-like matching keeps explicit variants such as "declined",
            # "delays", and "expired" inside the same deterministic metric.
            if all(term in text for term in terms):
                return metric, category
        category_terms = (
            ("Cybersecurity", ("cyber", "security", "breach", "vulnerability", "incident")),
            ("Legal", ("contract", "agreement", "legal", "compliance", "gdpr", "clause")),
            ("Supplier", ("supplier", "vendor", "delivery", "shipment", "logistics")),
            ("Customer", ("customer", "client", "account", "subscription", "complaint")),
            ("Financial", ("revenue", "cash", "debt", "margin", "profit", "cost", "budget")),
            ("Technology", ("system", "outage", "downtime", "backup", "migration", "api")),
            ("HR", ("employee", "staff", "resignation", "workforce", "hiring")),
            ("Operational", ("operation", "production", "manufacturing", "process", "capacity")),
        )
        for category, terms in category_terms:
            if any(term in text for term in terms):
                return "statement", category
        return "statement", "General"

    @staticmethod
    def _extract_value(text: str) -> tuple[Optional[float], Optional[str]]:
        percentage = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if percentage:
            return float(percentage.group(1)), "percent"
        currency = re.search(r"(?:€|\$|eur|usd)\s*(\d+(?:\.\d+)?)\s*([mk])?", text, re.I)
        if currency:
            multiplier = {"m": 1_000_000, "k": 1_000}.get((currency.group(2) or "").lower(), 1)
            return float(currency.group(1)) * multiplier, "currency"
        months = re.search(r"(\d+(?:\.\d+)?)\s*months?", text)
        if months:
            return float(months.group(1)), "months"
        return None, None

    @staticmethod
    def _scope(text: str) -> Optional[str]:
        if "top 5" in text or "five largest" in text:
            return "top_5_customers"
        if "one customer" in text or "one client" in text:
            return "single_customer"
        return None

    @staticmethod
    def _timeframe(text: str) -> Optional[str]:
        match = re.search(r"(?:within|in|next|during|over)\s+(\d+\s+(?:days?|weeks?|months?|years?))", text)
        return match.group(1) if match else None
