"""
Test configuration — forces all tests to use the deterministic rule engine
rather than hitting the live OpenRouter LLM API (which has unpredictable latency).
"""

import pytest


@pytest.fixture(autouse=True)
def force_rule_engine(monkeypatch):
    """
    Patches the settings singleton to blank out LLM API keys during testing.
    This ensures the risk analyzer always falls through to the fast deterministic
    rule engine, guaranteeing sub-second test execution and zero network dependency.
    """
    from app.config import settings

    # Patch the already-instantiated settings singleton directly
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    yield
