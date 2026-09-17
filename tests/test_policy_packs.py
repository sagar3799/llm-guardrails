from guardrails.policy import get_policy_engine
from guardrails.schemas import Action, Severity


def test_default_and_healthcare_pack_differ_on_pii_low_severity():
    default_engine = get_policy_engine()
    healthcare_engine = get_policy_engine("healthcare")
    assert default_engine.action_for("pii", Severity.LOW) == Action.WARN
    assert healthcare_engine.action_for("pii", Severity.LOW) == Action.BLOCK


def test_strict_pack_blocks_everything_at_low_severity_except_toxicity_warns():
    strict_engine = get_policy_engine("strict")
    assert strict_engine.action_for("prompt_injection", Severity.LOW) == Action.BLOCK
    assert strict_engine.action_for("pii", Severity.LOW) == Action.BLOCK
    assert strict_engine.action_for("toxicity", Severity.LOW) == Action.WARN


def test_enterprise_pack_matches_default_policy():
    default_engine = get_policy_engine()
    enterprise_engine = get_policy_engine("enterprise")
    for category in ("prompt_injection", "jailbreak", "pii", "toxicity"):
        for severity in (Severity.HIGH, Severity.MEDIUM, Severity.LOW):
            assert default_engine.action_for(category, severity) == enterprise_engine.action_for(category, severity)


def test_get_policy_engine_is_cached_per_name():
    a = get_policy_engine("strict")
    b = get_policy_engine("strict")
    assert a is b
    assert a is not get_policy_engine("healthcare")
