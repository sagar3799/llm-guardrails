"""Configurable pipeline of pluggable detectors — the extensibility layer on top of the
simple, zero-config check_input()/check_output() functions in middleware.py, which are
unaffected by anything here and remain the recommended entry point for the common case.

Use GuardrailsEngine when you want to register a custom detector, select a named policy
pack (see policy.py / policies/), or otherwise configure the pipeline beyond the
built-in defaults. See README: 'Pluggable detector interface' and 'Versioned policy
packs'.
"""

from __future__ import annotations

import time

from guardrails.builtin_detectors import (
    InjectionDetectorPlugin,
    PiiDetectorPlugin,
    ToxicityDetectorPlugin,
)
from guardrails.detector_base import DetectionSignal, Detector
from guardrails.middleware import _combine
from guardrails.policy import get_policy_engine
from guardrails.schemas import GuardResult
from guardrails.streaming import StreamingGuard

VALID_STAGES = ("input", "output")


class GuardrailsEngine:
    """Register a detector with register_detector(my_detector, stage="input") — anything
    implementing the Detector protocol (a check(text) -> DetectionSignal method) works,
    built-in or not; no subclassing or special base class required.
    """

    def __init__(self, policy_name: str | None = None) -> None:
        self._policy_engine = get_policy_engine(policy_name)
        self._detectors: dict[str, list[Detector]] = {
            "input": [InjectionDetectorPlugin(), PiiDetectorPlugin()],
            "output": [ToxicityDetectorPlugin(), PiiDetectorPlugin()],
        }

    def register_detector(self, detector: Detector, stage: str = "input") -> None:
        if stage not in VALID_STAGES:
            raise ValueError(f"stage must be one of {VALID_STAGES}, got {stage!r}")
        self._detectors[stage].append(detector)

    def check_input(self, text: str) -> GuardResult:
        return self._run(text, "input")

    def check_output(self, text: str) -> GuardResult:
        return self._run(text, "output")

    def _run(self, text: str, stage: str) -> GuardResult:
        start = time.perf_counter()
        signals: list[DetectionSignal] = [d.check(text) for d in self._detectors[stage]]
        triggers = [s for s in signals if s.triggered]
        latency_ms = (time.perf_counter() - start) * 1000
        return _combine(text, triggers, latency_ms, policy_engine=self._policy_engine)

    def create_streaming_guard(self, window_size: int = 40, stride: int = 20) -> StreamingGuard:
        """Builds a StreamingGuard that shares this engine's own registered output
        detectors and policy pack — so a custom detector registered here via
        register_detector(d, stage="output") is picked up by streaming too, closing the
        gap where the two execution paths used to diverge (docs/buildplan.md,
        Revision 6, known gap 1)."""
        return StreamingGuard(
            window_size=window_size,
            stride=stride,
            detectors=list(self._detectors["output"]),
            policy_engine=self._policy_engine,
        )
