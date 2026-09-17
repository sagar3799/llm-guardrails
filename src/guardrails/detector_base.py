from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from guardrails.schemas import Severity


def severity_from_score(score: float) -> Severity:
    """Fixed thresholds, model output only — see docs/buildplan.md, Revision 5 item 1.
    PolicyEngine decides the *action* per category from this; this function never does.
    Shared by every detector (built-in or custom) so severity means the same thing
    everywhere, regardless of which detector produced the confidence score."""
    if score >= 0.8:
        return Severity.HIGH
    if score >= 0.5:
        return Severity.MEDIUM
    return Severity.LOW


@dataclass
class DetectionSignal:
    """What every detector — built-in or custom — returns from check(). Only signals
    with triggered=True get combined into a GuardResult (see middleware._combine and
    engine.GuardrailsEngine._run)."""

    triggered: bool
    category: str
    confidence: float
    reason: str
    matched_rules: list[str] = field(default_factory=list)

    @property
    def severity(self) -> Severity:
        return severity_from_score(self.confidence)


class Detector(Protocol):
    """Interface a detector — built-in or custom — must implement to be registered with
    GuardrailsEngine.register_detector(). A Protocol, not an ABC: any object with a
    matching check(text) method works, no subclassing required. See README:
    'Pluggable detector interface'."""

    def check(self, text: str) -> DetectionSignal: ...
