"""
AI Risk Analyst — Enterprise Security, PII Masking, Prompt Injection Defense, and Audit Logging.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple


class SecuritySanitizer:
    """
    Protects the AI system against Prompt Injection and masks Personally Identifiable Information (PII).
    """

    # Common PII Regex Patterns
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
    IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")

    # Prompt Injection Attack Patterns
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
        re.compile(r"system\s*:\s*override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
        re.compile(r"disregard\s+(?:all\s+)?rules", re.IGNORECASE),
        re.compile(r"reveal\s+(?:your\s+)?(?:system\s+prompt|hidden\s+instructions)", re.IGNORECASE),
        re.compile(r"jailbreak", re.IGNORECASE),
        re.compile(r"DAN\s+mode", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_input(cls, text: str) -> Tuple[str, List[str]]:
        """
        Masks PII and strips prompt injection attempts.
        Returns: (sanitized_text, list_of_security_warnings)
        """
        warnings: List[str] = []
        sanitized = text

        # 1. Prompt Injection Detection
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(sanitized):
                warnings.append("Security Alert: Potential Prompt Injection attempt detected and neutralized.")
                sanitized = pattern.sub("[REDACTED_ADVERSARIAL_INSTRUCTION]", sanitized)

        # 2. PII Masking
        if cls.EMAIL_PATTERN.search(sanitized):
            sanitized = cls.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)
            warnings.append("PII Notice: Email address masked for privacy protection.")

        if cls.PHONE_PATTERN.search(sanitized):
            sanitized = cls.PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)
            warnings.append("PII Notice: Phone number masked for privacy protection.")

        if cls.CREDIT_CARD_PATTERN.search(sanitized):
            sanitized = cls.CREDIT_CARD_PATTERN.sub("[REDACTED_FINANCIAL_CARD]", sanitized)
            warnings.append("PII Notice: Financial payment card number masked.")

        if cls.IBAN_PATTERN.search(sanitized):
            sanitized = cls.IBAN_PATTERN.sub("[REDACTED_IBAN]", sanitized)
            warnings.append("PII Notice: Bank IBAN number masked.")

        return sanitized, warnings


class AuditLogger:
    """
    Maintains an immutable enterprise audit trail for all risk assessments.
    Logs who, when, what documents, model version, and risk results.
    """

    def __init__(self, log_dir: str = "data/audit"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "audit_trail.jsonl")

    def record_event(
        self,
        event_type: str,
        user_or_session_id: str,
        model_used: str,
        input_summary: str,
        overall_risk: str,
        risks_detected: List[str],
        execution_time_seconds: float,
        security_warnings: List[str] = None,
    ) -> Dict[str, Any]:
        """Appends an audit record to the immutable JSONL log."""
        record = {
            "audit_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "session_id": user_or_session_id,
            "model": model_used,
            "input_char_length": len(input_summary),
            "input_snippet": input_summary[:120].replace("\n", " "),
            "overall_risk": overall_risk,
            "risks_detected": risks_detected,
            "execution_time_seconds": execution_time_seconds,
            "security_warnings": security_warnings or [],
        }

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            print(f"[AuditLogger Error] Could not write audit log: {e}")

        return record


# Global instances
security_sanitizer = SecuritySanitizer()
audit_logger = AuditLogger()
