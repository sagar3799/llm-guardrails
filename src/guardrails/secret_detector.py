from __future__ import annotations

import re
from dataclasses import dataclass, field

# Presidio's built-in recognizers don't cover API keys/secrets at all — this gap was
# found empirically by eval/run_output_redteam.py (0/3 api_key_leak cases caught before
# this existed). Same regex-fallback approach already used in injection_detector.py's
# jailbreak patterns, applied to a different leak category — not a new detection
# *approach*, just a missing pattern set for an in-scope category (sensitive-data leakage).
SECRET_PATTERNS = {
    "AWS_ACCESS_KEY": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GITHUB_TOKEN": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "OPENAI_API_KEY": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "SLACK_TOKEN": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "PRIVATE_KEY_BLOCK": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GENERIC_SECRET_ASSIGNMENT": re.compile(
        r"(?i)\b(api[_-]?key|secret|access[_-]?token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"
    ),
}


@dataclass
class SecretSignal:
    has_secret: bool
    matched_types: list[str] = field(default_factory=list)
    confidence: float = 0.0


class SecretDetector:
    """Regex-only, no model to load — fast and deterministic by design, since a secret
    pattern either matches or it doesn't; there's no ambiguity worth a classifier here."""

    def check(self, text: str) -> SecretSignal:
        matched = [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]
        if not matched:
            return SecretSignal(has_secret=False)
        return SecretSignal(has_secret=True, matched_types=matched, confidence=0.95)


_detector = SecretDetector()


def get_secret_detector() -> SecretDetector:
    """Stateless and cheap to construct — no lru_cache needed, unlike the ML detectors."""
    return _detector
