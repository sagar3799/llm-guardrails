"""Sanity-checks the mechanism run_policy_comparison.py depends on: that policies
change hard-block behavior for PII without changing whether detection fires at all.
The full comparison script itself is exercised manually (it writes a report), not as
a unit test — this locks in the underlying claim so it can't silently drift."""

from guardrails.engine import GuardrailsEngine
from guardrails.schemas import Action

PII_TEXT = "My email is sagar.meena@example.com."


def test_pii_hard_blocks_under_strict_and_healthcare_but_not_default_or_enterprise():
    results = {
        policy: GuardrailsEngine(policy_name=policy).check_input(PII_TEXT).action
        for policy in (None, "strict", "healthcare", "enterprise")
    }
    assert results[None] == Action.ANONYMIZE
    assert results["enterprise"] == Action.ANONYMIZE
    assert results["strict"] == Action.BLOCK
    assert results["healthcare"] == Action.BLOCK


def test_all_policies_still_detect_pii_even_when_action_differs():
    for policy in (None, "strict", "healthcare", "enterprise"):
        result = GuardrailsEngine(policy_name=policy).check_input(PII_TEXT)
        assert "pii" in result.categories
        assert result.action != Action.ALLOW
