from __future__ import annotations

from guardrails.detector_base import DetectionSignal
from guardrails.middleware import _combine, _pii_trigger
from guardrails.schemas import GuardResult
from guardrails.toxicity_detector import get_toxicity_detector


class StreamingGuard:
    """Reusable sliding-window guard for token-by-token (streaming) output.

    Buffering the full response before checking it defeats time-to-first-token in any
    real streaming LLM app — see docs/buildplan.md, Phase 5. This runs the toxicity/PII
    checks on an overlapping window of the last `window_size` tokens, re-evaluated every
    `stride` tokens, instead of waiting for the full response.

    Scope, stated honestly (docs/buildplan.md, Phase 5): this demonstrates the approach
    and its tradeoffs on a simulated token stream — it is not wired to a real LLM's
    token stream or its BPE tokenizer (see Implementation notes, item 2: windowing here
    operates on whitespace-delimited tokens, not real subword tokens).
    """

    def __init__(self, window_size: int = 40, stride: int = 20) -> None:
        if stride >= window_size:
            raise ValueError("stride must be smaller than window_size for windows to overlap")
        self.window_size = window_size
        self.stride = stride
        self._buffer: list[str] = []
        self._tokens_since_last_check = 0

    def feed(self, token: str) -> list[GuardResult]:
        """Append one token; return any GuardResults triggered by checking the current
        window. Returns an empty list if the window isn't full yet or nothing fired."""
        self._buffer.append(token)
        if len(self._buffer) > self.window_size:
            self._buffer = self._buffer[-self.window_size :]
        self._tokens_since_last_check += 1

        ready = len(self._buffer) == self.window_size and self._tokens_since_last_check >= self.stride
        if not ready:
            return []

        self._tokens_since_last_check = 0
        window_text = " ".join(self._buffer)
        return self._check_window(window_text)

    def _check_window(self, window_text: str) -> list[GuardResult]:
        triggers: list[DetectionSignal] = []
        toxicity_signal = get_toxicity_detector().check(window_text)
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
        pii_trigger = _pii_trigger(window_text)
        if pii_trigger:
            triggers.append(pii_trigger)

        if not triggers:
            return []
        return [_combine(window_text, triggers, latency_ms=0.0)]

    def flush(self) -> list[GuardResult]:
        """Check whatever remains in the buffer at end-of-stream, even if it never hit
        a full stride boundary."""
        if not self._buffer:
            return []
        window_text = " ".join(self._buffer)
        return self._check_window(window_text)
