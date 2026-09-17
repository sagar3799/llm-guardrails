"""Adapts the three built-in detectors to the Detector protocol (detector_base.py) so
GuardrailsEngine can treat them the same way it treats a custom, user-registered
detector. The underlying detector classes (InjectionDetector, PiiDetector,
ToxicityDetector) are unchanged and keep their own direct APIs — these are thin wrappers,
not replacements."""

from __future__ import annotations

from guardrails.detector_base import DetectionSignal
from guardrails.injection_detector import get_detector
from guardrails.pii_detector import get_pii_detector
from guardrails.toxicity_detector import get_toxicity_detector


class InjectionDetectorPlugin:
    category = "prompt_injection"

    def check(self, text: str) -> DetectionSignal:
        signal = get_detector().check(text)
        return DetectionSignal(
            triggered=signal.is_injection,
            category=self.category,
            reason=f"blocked: prompt_injection, confidence {signal.confidence:.2f}",
            confidence=signal.confidence,
            matched_rules=signal.matched_rules,
        )


class PiiDetectorPlugin:
    category = "pii"

    def check(self, text: str) -> DetectionSignal:
        signal = get_pii_detector().check(text)
        entity_list = ", ".join(signal.entity_types)
        return DetectionSignal(
            triggered=signal.has_pii,
            category=self.category,
            reason=f"flagged: pii_detected, type={entity_list}",
            confidence=signal.confidence,
            matched_rules=signal.matched_rules,
        )


class ToxicityDetectorPlugin:
    category = "toxicity"

    def check(self, text: str) -> DetectionSignal:
        signal = get_toxicity_detector().check(text)
        return DetectionSignal(
            triggered=signal.is_toxic,
            category=self.category,
            reason=f"blocked: toxicity, confidence {signal.confidence:.2f}",
            confidence=signal.confidence,
            matched_rules=signal.matched_rules,
        )
