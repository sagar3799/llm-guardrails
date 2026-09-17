from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_NAME = "unitary/toxic-bert"
# Same one-time-conversion caching pattern as injection_detector.py — see
# docs/buildplan.md, Revision 2 item 1 for the PyTorch-at-conversion-time caveat.
ONNX_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".onnx_cache" / "toxicity_model"


@dataclass
class ToxicitySignal:
    is_toxic: bool
    confidence: float
    matched_rules: list[str] = field(default_factory=list)


class ToxicityDetector:
    """Local toxicity classifier for output-side content checks.

    `unitary/toxic-bert` is a multi-label classifier (toxic, severe_toxic, obscene,
    threat, insult, identity_hate) — we treat any label crossing the threshold as toxic
    and report the max score as confidence, with the specific label(s) as matched_rules.
    """

    def __init__(self, threshold: float = 0.5) -> None:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer

        self.threshold = threshold
        if ONNX_CACHE_DIR.exists() and any(ONNX_CACHE_DIR.glob("*.onnx")):
            self.tokenizer = AutoTokenizer.from_pretrained(ONNX_CACHE_DIR)
            self.model = ORTModelForSequenceClassification.from_pretrained(ONNX_CACHE_DIR)
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            self.model = ORTModelForSequenceClassification.from_pretrained(MODEL_NAME, export=True)
            ONNX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self.model.save_pretrained(ONNX_CACHE_DIR)
            self.tokenizer.save_pretrained(ONNX_CACHE_DIR)
        self.id2label = self.model.config.id2label

    def _sigmoid(self, x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    def check(self, text: str) -> ToxicitySignal:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        outputs = self.model(**inputs)
        logits = outputs.logits.detach().numpy()[0]
        scores = self._sigmoid(logits)

        hits = [(self.id2label[i], float(scores[i])) for i in range(len(scores)) if scores[i] >= self.threshold]
        if not hits:
            return ToxicitySignal(is_toxic=False, confidence=float(scores.max()))

        confidence = max(score for _, score in hits)
        matched_rules = [f"toxicity_classifier:{label}" for label, _ in hits]
        return ToxicitySignal(is_toxic=True, confidence=confidence, matched_rules=matched_rules)


@lru_cache(maxsize=1)
def get_toxicity_detector() -> ToxicityDetector:
    """Process-wide singleton so the model is loaded/converted once, not per call."""
    return ToxicityDetector()
