from guardrails.policy import PolicyEngine
from guardrails.schemas import Action, Severity


def test_action_for_category_and_severity():
    engine = PolicyEngine()
    assert engine.action_for("prompt_injection", Severity.HIGH) == Action.BLOCK
    assert engine.action_for("pii", Severity.HIGH) == Action.ANONYMIZE
    assert engine.action_for("toxicity", Severity.LOW) == Action.ALLOW


def test_same_severity_different_action_across_categories():
    """Proves severity and action are genuinely decoupled, not aliases of each other —
    the same HIGH severity maps to BLOCK for toxicity but ANONYMIZE for pii, because
    policy.yaml says so per-category, not because of anything in the severity itself."""
    engine = PolicyEngine()
    assert engine.action_for("toxicity", Severity.HIGH) == Action.BLOCK
    assert engine.action_for("pii", Severity.HIGH) == Action.ANONYMIZE


def test_conflict_resolution_most_restrictive_wins():
    engine = PolicyEngine()
    action = engine.decide([("pii", Severity.HIGH), ("prompt_injection", Severity.HIGH)])
    assert action == Action.BLOCK


def test_conflict_resolution_is_order_independent():
    engine = PolicyEngine()
    a = engine.decide([("prompt_injection", Severity.HIGH), ("pii", Severity.HIGH)])
    b = engine.decide([("pii", Severity.HIGH), ("prompt_injection", Severity.HIGH)])
    assert a == b == Action.BLOCK


def test_no_triggers_allows():
    engine = PolicyEngine()
    assert engine.decide([]) == Action.ALLOW


def test_unknown_category_defaults_to_warn():
    engine = PolicyEngine()
    assert engine.action_for("unknown_category", Severity.HIGH) == Action.WARN
