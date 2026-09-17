from __future__ import annotations

from functools import lru_cache

from guardrails.pii_detector import get_pii_detector


class PiiAnonymizer:
    """Redacts PII in text via Presidio's AnonymizerEngine.

    Reuses the same AnalyzerEngine instance as PiiDetector (Phase 1) to find entities —
    detection logic isn't duplicated, only the redaction step is new here (Phase 2.5).
    This is one-way: placeholders replace the original values, which are never
    reconstructed or re-injected anywhere downstream (docs/buildplan.md, Implementation
    notes item 3) — the goal is keeping PII from ever reaching a third-party LLM or a
    logging/training pipeline, not masking-and-later-unmasking it.
    """

    def __init__(self) -> None:
        from presidio_anonymizer import AnonymizerEngine

        self._detector = get_pii_detector()
        self._anonymizer = AnonymizerEngine()

    def anonymize(self, text: str) -> str:
        analyzer_results = self._detector.analyzer.analyze(
            text=text, language="en", entities=self._detector.entities
        )
        hits = [r for r in analyzer_results if r.score >= self._detector.threshold]
        if not hits:
            return text
        result = self._anonymizer.anonymize(text=text, analyzer_results=hits)
        return result.text


@lru_cache(maxsize=1)
def get_pii_anonymizer() -> PiiAnonymizer:
    return PiiAnonymizer()
