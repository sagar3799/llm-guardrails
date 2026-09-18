from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_NAME = "protectai/deberta-v3-base-prompt-injection-v2"
# One-time ONNX conversion is cached here so subsequent process starts load directly
# instead of re-exporting (~30-60s) every time — see docs/buildplan.md, Revision 2 item 1.
ONNX_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".onnx_cache" / "injection_model"

# Known jailbreak / injection phrasings, kept as an independent second signal alongside
# the classifier — not a replacement for it. Catches well-known phrasings verbatim even
# if the classifier's confidence on a given paraphrase is borderline.
JAILBREAK_PATTERNS = [
    re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.IGNORECASE),
    re.compile(r"disregard (all |any )?(prior|previous) (instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"you are now (in )?(dan|developer mode|jailbreak(ed)?)", re.IGNORECASE),
    re.compile(r"pretend (you have no|you'?re not bound by) (restrictions|rules|guidelines)", re.IGNORECASE),
    re.compile(r"forget (that )?you'?re (an )?ai", re.IGNORECASE),
    re.compile(r"system prompt override", re.IGNORECASE),
    re.compile(r"reveal your (system prompt|instructions)", re.IGNORECASE),
    re.compile(r"act as if you have no (content )?filter", re.IGNORECASE),
]


@dataclass
class InjectionSignal:
    is_injection: bool
    confidence: float
    matched_rules: list[str] = field(default_factory=list)


class InjectionDetector:
    """Local prompt-injection / jailbreak detector.

    Combines a purpose-built classifier (protectai/deberta-v3-base-prompt-injection-v2,
    loaded via optimum/onnxruntime) with a regex fallback list for well-known jailbreak
    phrasings. Both signals run fully locally once the model is cached on first load —
    see docs/buildplan.md, Revision 2 item 1 for the one-time PyTorch conversion caveat.
    """

    def __init__(self, model_name: str = MODEL_NAME, threshold: float = 0.5) -> None:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer

        self.threshold = threshold
        if ONNX_CACHE_DIR.exists() and any(ONNX_CACHE_DIR.glob("*.onnx")):
            self.tokenizer = AutoTokenizer.from_pretrained(ONNX_CACHE_DIR)
            self.model = ORTModelForSequenceClassification.from_pretrained(ONNX_CACHE_DIR)
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = ORTModelForSequenceClassification.from_pretrained(model_name, export=True)
            ONNX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self.model.save_pretrained(ONNX_CACHE_DIR)
            self.tokenizer.save_pretrained(ONNX_CACHE_DIR)
        self.injection_label_id = self._resolve_injection_label_id()

    def _resolve_injection_label_id(self) -> int:
        id2label = self.model.config.id2label
        for idx, label in id2label.items():
            if "injection" in str(label).lower() or "inject" in str(label).lower():
                return int(idx)
        # fall back to the conventional "positive class" id if labels aren't named
        return max(int(k) for k in id2label)

    def _classifier_score(self, text: str) -> float:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        outputs = self.model(**inputs)
        logits = outputs.logits.detach().numpy()[0]
        probs = np.exp(logits) / np.exp(logits).sum()
        return float(probs[self.injection_label_id])

    def _regex_matches(self, text: str) -> list[str]:
        return [f"regex:{p.pattern}" for p in JAILBREAK_PATTERNS if p.search(text)]

    def check(self, text: str) -> InjectionSignal:
        confidence = self._classifier_score(text)
        regex_hits = self._regex_matches(text)
        is_injection = confidence >= self.threshold or bool(regex_hits)

        matched_rules: list[str] = []
        if confidence >= self.threshold:
            matched_rules.append("injection_classifier")
        matched_rules.extend(regex_hits)

        if regex_hits and confidence < self.threshold:
            # a known phrasing matched even though the classifier scored it low —
            # don't under-report the confidence in the explainability log because of it.
            confidence = max(confidence, 0.75)

        return InjectionSignal(is_injection=is_injection, confidence=confidence, matched_rules=matched_rules)


@lru_cache(maxsize=1)
def get_detector() -> InjectionDetector:
    """Process-wide singleton so the model is loaded/converted once, not per call."""
    return InjectionDetector()


def category_for(matched_rules: list[str]) -> str:
    """Distinguishes prompt_injection (the ML classifier itself fired, confidence over
    threshold) from jailbreak (only the regex fallback caught a known phrasing) —
    policy.yaml has always defined both as separate categories, but every caller used to
    hardcode "prompt_injection" regardless of which signal actually fired, making the
    jailbreak policy entry unreachable. Regression-tested in test_pipeline.py and
    test_engine.py (both code paths)."""
    return "prompt_injection" if "injection_classifier" in matched_rules else "jailbreak"
