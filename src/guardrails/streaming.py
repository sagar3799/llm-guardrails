from __future__ import annotations

from guardrails.builtin_detectors import (
    PiiDetectorPlugin,
    SecretDetectorPlugin,
    ToxicityDetectorPlugin,
)
from guardrails.detector_base import Detector
from guardrails.middleware import _combine
from guardrails.policy import PolicyEngine
from guardrails.schemas import GuardResult


class StreamingGuard:
    """Reusable sliding-window guard for token-by-token (streaming) output.

    Buffering the full response before checking it defeats time-to-first-token in any
    real streaming LLM app — see docs/buildplan.md, Phase 5. This runs the registered
    detectors on an overlapping window of the last `window_size` tokens, re-evaluated
    every `stride` tokens, instead of waiting for the full response.

    Uses the same Detector protocol as GuardrailsEngine (detector_base.py) — pass
    `detectors`/`policy_engine` explicitly, or build one via
    `GuardrailsEngine.create_streaming_guard()` to automatically reuse that engine's own
    registered detectors and policy pack. Constructing a StreamingGuard directly with no
    arguments still works and defaults to the same built-in toxicity+PII checks as
    before — this unification didn't change default behavior, just where the detector
    list comes from.

    Scope, stated honestly (docs/buildplan.md, Phase 5): this demonstrates the approach
    and its tradeoffs on a simulated token stream — it is not wired to a real LLM's
    token stream or its BPE tokenizer (see Implementation notes, item 2: windowing here
    operates on whitespace-delimited tokens, not real subword tokens).
    """

    def __init__(
        self,
        window_size: int = 40,
        stride: int = 20,
        detectors: list[Detector] | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        if stride >= window_size:
            raise ValueError("stride must be smaller than window_size for windows to overlap")
        self.window_size = window_size
        self.stride = stride
        self.detectors = (
            detectors
            if detectors is not None
            else [ToxicityDetectorPlugin(), PiiDetectorPlugin(), SecretDetectorPlugin()]
        )
        self.policy_engine = policy_engine
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
        signals = [d.check(window_text) for d in self.detectors]
        triggers = [s for s in signals if s.triggered]
        if not triggers:
            return []
        return [_combine(window_text, triggers, latency_ms=0.0, policy_engine=self.policy_engine)]

    def flush(self) -> list[GuardResult]:
        """Check whatever remains in the buffer at end-of-stream, even if it never hit
        a full stride boundary."""
        if not self._buffer:
            return []
        window_text = " ".join(self._buffer)
        return self._check_window(window_text)
