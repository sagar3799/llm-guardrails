from __future__ import annotations

import json
import logging

from guardrails.detector_base import DetectionSignal
from guardrails.injection_detector import category_for, get_detector
from guardrails.pii_anonymizer import get_pii_anonymizer
from guardrails.pii_detector import get_pii_detector
from guardrails.policy import PolicyEngine, get_policy_engine
from guardrails.schemas import Action, GuardResult, Severity
from guardrails.secret_detector import get_secret_detector
from guardrails.toxicity_detector import get_toxicity_detector

logger = logging.getLogger("guardrails")

_SEVERITY_RANK = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}


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


def _combine(
    text: str,
    triggers: list[DetectionSignal],
    latency_ms: float,
    policy_engine: PolicyEngine | None = None,
) -> GuardResult:
    """Shared by check_input/check_output (and GuardrailsEngine) so all of them return
    the same GuardResult shape.

    Action comes from the PolicyEngine (category + severity -> action, configurable via
    policy.yaml or a named pack under policies/), with BLOCK > ANONYMIZE > WARN > ALLOW
    conflict resolution across categories when more than one triggers on the same input
    (Revision 4, item 2). `policy_engine` defaults to the root policy.yaml — pass a
    different one (e.g. get_policy_engine("healthcare")) to use a named pack instead.
    """
    policy_engine = policy_engine or get_policy_engine()

    if not triggers:
        result = GuardResult(allowed=True, action=Action.ALLOW, severity=Severity.LOW)
        _log_if_notable(result, latency_ms)
        return result

    category_severities = [(t.category, t.severity) for t in triggers]
    action = policy_engine.decide(category_severities)
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


def _injection_trigger(text: str) -> DetectionSignal | None:
    """category is prompt_injection when the ML classifier itself fired, jailbreak when
    only the regex fallback caught a known phrasing — see
    injection_detector.category_for for why this distinction used to be lost."""
    injection_signal = get_detector().check(text)
    if not injection_signal.is_injection:
        return None
    category = category_for(injection_signal.matched_rules)
    return DetectionSignal(
        triggered=True,
        category=category,
        reason=f"blocked: {category}, confidence {injection_signal.confidence:.2f}",
        confidence=injection_signal.confidence,
        matched_rules=injection_signal.matched_rules,
    )


def _pii_trigger(text: str) -> DetectionSignal | None:
    """Same Presidio wrapper for both input and output — different call site, no
    duplicated detection logic (see docs/buildplan.md, Phase 2)."""
    pii_signal = get_pii_detector().check(text)
    if not pii_signal.has_pii:
        return None
    entity_list = ", ".join(pii_signal.entity_types)
    return DetectionSignal(
        triggered=True,
        category="pii",
        reason=f"flagged: pii_detected, type={entity_list}",
        confidence=pii_signal.confidence,
        matched_rules=pii_signal.matched_rules,
    )


def _secret_trigger(text: str) -> DetectionSignal | None:
    """Same regex detector for both input and output — a pasted secret in a user's
    prompt is as worth catching as one leaked in a generated response."""
    secret_signal = get_secret_detector().check(text)
    if not secret_signal.has_secret:
        return None
    return DetectionSignal(
        triggered=True,
        category="secret_leak",
        reason=f"blocked: secret_leak, type={', '.join(secret_signal.matched_types)}",
        confidence=secret_signal.confidence,
        matched_rules=[f"secret:{t}" for t in secret_signal.matched_types],
    )


def check_input(text: str) -> GuardResult:
    """Input-side guardrails: prompt injection/jailbreak detection, PII detection, and
    secret/API-key detection.

    The simple, zero-config entry point — for a configurable set of detectors and/or a
    named policy pack, use GuardrailsEngine instead (see engine.py).
    """
    import time

    start = time.perf_counter()
    triggers: list[DetectionSignal] = []

    injection_trigger = _injection_trigger(text)
    if injection_trigger:
        triggers.append(injection_trigger)

    pii_trigger = _pii_trigger(text)
    if pii_trigger:
        triggers.append(pii_trigger)

    secret_trigger = _secret_trigger(text)
    if secret_trigger:
        triggers.append(secret_trigger)

    latency_ms = (time.perf_counter() - start) * 1000
    return _combine(text, triggers, latency_ms)


def check_output(text: str) -> GuardResult:
    """Output-side guardrails: toxicity detection, PII leak detection, and
    secret/API-key leak detection."""
    import time

    start = time.perf_counter()
    triggers: list[DetectionSignal] = []

    toxicity_signal = get_toxicity_detector().check(text)
    if toxicity_signal.is_toxic:
        triggers.append(
            DetectionSignal(
                triggered=True,
                category="toxicity",
                reason=f"blocked: toxicity, confidence {toxicity_signal.confidence:.2f}",
                confidence=toxicity_signal.confidence,
                matched_rules=toxicity_signal.matched_rules,
            )
        )

    pii_trigger = _pii_trigger(text)
    if pii_trigger:
        triggers.append(pii_trigger)

    secret_trigger = _secret_trigger(text)
    if secret_trigger:
        triggers.append(secret_trigger)

    latency_ms = (time.perf_counter() - start) * 1000
    return _combine(text, triggers, latency_ms)
