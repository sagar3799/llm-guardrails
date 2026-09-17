from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from guardrails.injection_detector import get_detector
from guardrails.pii_anonymizer import get_pii_anonymizer
from guardrails.pii_detector import get_pii_detector
from guardrails.policy import get_policy_engine
from guardrails.schemas import Action, GuardResult, Severity
from guardrails.toxicity_detector import get_toxicity_detector

logger = logging.getLogger("guardrails")

_SEVERITY_RANK = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}


def _severity_from_score(score: float) -> Severity:
    # Fixed thresholds, model output only — see docs/buildplan.md, Revision 5 item 1.
    # PolicyEngine decides the *action* per category from this; this function never does.
    if score >= 0.8:
        return Severity.HIGH
    if score >= 0.5:
        return Severity.MEDIUM
    return Severity.LOW


@dataclass
class _Trigger:
    category: str
    reason: str
    confidence: float
    matched_rules: list[str] = field(default_factory=list)

    @property
    def severity(self) -> Severity:
        return _severity_from_score(self.confidence)


def _log_if_notable(result: GuardResult, latency_ms: float) -> None:
    if result.action == Action.ALLOW:
        return
    logger.info(
        json.dumps(
            {
                "action": result.action.value,
                "severity": result.severity.value,
                "risk_score": result.risk_score,
                "categories": result.categories,
                "matched_rules": result.matched_rules,
                "latency_ms": round(latency_ms, 2),
            }
        )
    )


def _combine(text: str, triggers: list[_Trigger], latency_ms: float) -> GuardResult:
    """Shared by check_input/check_output so both return the same GuardResult shape.

    Action comes from the PolicyEngine (category + severity -> action, configurable via
    policy.yaml), with BLOCK > ANONYMIZE > WARN > ALLOW conflict resolution across
    categories when more than one triggers on the same input (Revision 4, item 2).
    """
    if not triggers:
        result = GuardResult(allowed=True, action=Action.ALLOW, severity=Severity.LOW)
        _log_if_notable(result, latency_ms)
        return result

    category_severities = [(t.category, t.severity) for t in triggers]
    action = get_policy_engine().decide(category_severities)
    risk_score = max(t.confidence for t in triggers)
    overall_severity = max((sev for _, sev in category_severities), key=lambda s: _SEVERITY_RANK[s])

    sanitized_text = get_pii_anonymizer().anonymize(text) if action == Action.ANONYMIZE else None

    result = GuardResult(
        allowed=action != Action.BLOCK,
        reasons=[t.reason for t in triggers],
        categories=[t.category for t in triggers],
        action=action,
        sanitized_text=sanitized_text,
        risk_score=risk_score,
        matched_rules=[rule for t in triggers for rule in t.matched_rules],
        severity=overall_severity,
    )
    _log_if_notable(result, latency_ms)
    return result


def _pii_trigger(text: str) -> _Trigger | None:
    """Same Presidio wrapper for both input and output — different call site, no
    duplicated detection logic (see docs/buildplan.md, Phase 2)."""
    pii_signal = get_pii_detector().check(text)
    if not pii_signal.has_pii:
        return None
    entity_list = ", ".join(pii_signal.entity_types)
    return _Trigger(
        category="pii",
        reason=f"flagged: pii_detected, type={entity_list}",
        confidence=pii_signal.confidence,
        matched_rules=pii_signal.matched_rules,
    )


def check_input(text: str) -> GuardResult:
    """Input-side guardrails: prompt injection/jailbreak detection + PII detection."""
    import time

    start = time.perf_counter()
    triggers: list[_Trigger] = []

    injection_signal = get_detector().check(text)
    if injection_signal.is_injection:
        triggers.append(
            _Trigger(
                category="prompt_injection",
                reason=f"blocked: prompt_injection, confidence {injection_signal.confidence:.2f}",
                confidence=injection_signal.confidence,
                matched_rules=injection_signal.matched_rules,
            )
        )

    pii_trigger = _pii_trigger(text)
    if pii_trigger:
        triggers.append(pii_trigger)

    latency_ms = (time.perf_counter() - start) * 1000
    return _combine(text, triggers, latency_ms)


def check_output(text: str) -> GuardResult:
    """Output-side guardrails: toxicity detection + PII leak detection."""
    import time

    start = time.perf_counter()
    triggers: list[_Trigger] = []

    toxicity_signal = get_toxicity_detector().check(text)
    if toxicity_signal.is_toxic:
        triggers.append(
            _Trigger(
                category="toxicity",
                reason=f"blocked: toxicity, confidence {toxicity_signal.confidence:.2f}",
                confidence=toxicity_signal.confidence,
                matched_rules=toxicity_signal.matched_rules,
            )
        )

    pii_trigger = _pii_trigger(text)
    if pii_trigger:
        triggers.append(pii_trigger)

    latency_ms = (time.perf_counter() - start) * 1000
    return _combine(text, triggers, latency_ms)
