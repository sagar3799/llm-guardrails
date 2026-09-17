from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

SPACY_MODEL = "en_core_web_lg"
# en_core_web_lg (~560MB) has materially better name recall than en_core_web_sm — see
# docs/buildplan.md, Revision 2 item 2. Swap models here if setup weight ever matters
# more than name-recall accuracy for a given deployment.

DEFAULT_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "PERSON",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
]
# LOCATION deliberately excluded: Presidio's spaCy-backed LOCATION recognizer tags broad
# geographic mentions (countries, regions, cities — e.g. "northern Europe") the same way
# it would tag a precise street address. Broad locations aren't meaningfully PII in most
# product contexts and produced a real false positive during Phase 3 red-teaming (see
# eval/results.md). PERSON is kept despite its own known limitation — spaCy NER can't
# distinguish a real person's name from a fictional/famous one (also documented in
# eval/results.md) — because dropping it would defeat name-PII detection entirely; that
# tradeoff is judged worth keeping, the LOCATION one wasn't.


@dataclass
class PiiSignal:
    has_pii: bool
    entity_types: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    confidence: float = 0.0


class PiiDetector:
    """Local PII detector wrapping Microsoft Presidio's AnalyzerEngine.

    Standalone by design (Phase 1, Day 2-3) — no anonymization here, that's Phase 2.5's
    job via a separate `pii_anonymizer.py` wrapper around the same detections.
    """

    def __init__(self, entities: list[str] | None = None, threshold: float = 0.4) -> None:
        # 0.4, not 0.5: Presidio's PhoneRecognizer scores a plain pattern match like
        # "(415) 555-0198" at ~0.4 confidence by default — well below EMAIL_ADDRESS's
        # ~1.0 regex match or PERSON's ~0.85 spaCy NER score. A single flat threshold
        # across entity types with very different natural confidence bands means picking
        # the lowest one that doesn't start producing false positives on clean text,
        # not 0.5 as an arbitrary default.
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        self.entities = entities or DEFAULT_ENTITIES
        self.threshold = threshold

        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()
        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])

    def check(self, text: str) -> PiiSignal:
        results = self.analyzer.analyze(text=text, language="en", entities=self.entities)
        hits = [r for r in results if r.score >= self.threshold]
        if not hits:
            return PiiSignal(has_pii=False)

        entity_types = sorted({r.entity_type for r in hits})
        matched_rules = [f"presidio:{r.entity_type}" for r in hits]
        confidence = max(r.score for r in hits)
        return PiiSignal(
            has_pii=True,
            entity_types=entity_types,
            matched_rules=matched_rules,
            confidence=confidence,
        )


@lru_cache(maxsize=1)
def get_pii_detector() -> PiiDetector:
    """Process-wide singleton so the spaCy pipeline is loaded once, not per call."""
    return PiiDetector()
