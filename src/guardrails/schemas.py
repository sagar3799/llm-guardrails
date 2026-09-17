from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Action(str, Enum):
    BLOCK = "block"
    ANONYMIZE = "anonymize"
    WARN = "warn"
    ALLOW = "allow"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GuardResult(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    action: Action = Action.ALLOW
    sanitized_text: str | None = None
    risk_score: float | None = None
    matched_rules: list[str] = Field(default_factory=list)
    severity: Severity = Severity.LOW
