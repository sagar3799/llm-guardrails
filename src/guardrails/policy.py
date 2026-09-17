from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

from guardrails.schemas import Action, Severity

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent.parent / "policy.yaml"
# Named policy packs (strict/enterprise/healthcare/...) live under policies/<name>.yaml
# — see README: "Versioned policy packs". The root policy.yaml stays the zero-config
# default; packs are opt-in via get_policy_engine("<name>").
POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "policies"

# BLOCK > ANONYMIZE > WARN > ALLOW — most-restrictive wins, always.
# See docs/buildplan.md, Revision 4 item 2: without this fixed order, an input tripping
# two categories with different resulting actions would resolve however the code happens
# to iterate, which is nondeterministic behavior in a safety-critical path.
_ACTION_PRIORITY = {
    Action.BLOCK: 3,
    Action.ANONYMIZE: 2,
    Action.WARN: 1,
    Action.ALLOW: 0,
}


class PolicyEngine:
    """Maps (category, severity) -> Action via a configurable policy.yaml.

    Severity is a pure model output (see schemas.Severity / detector_base.severity_from_score)
    — this class only encodes business policy: what to DO about a given severity, and
    that can differ per category (docs/buildplan.md, Revision 5 item 1). Keep the
    per-category lookup dumb on purpose — a dict with a default — the interesting part is
    that it's configurable, not that it's clever.
    """

    def __init__(self, policy_path: Path | str = DEFAULT_POLICY_PATH) -> None:
        with open(policy_path, encoding="utf-8") as f:
            self._policy: dict[str, dict[str, str]] = yaml.safe_load(f)

    def action_for(self, category: str, severity: Severity) -> Action:
        category_policy = self._policy.get(category, {})
        action_str = category_policy.get(severity.value, "warn")
        return Action(action_str)

    def decide(self, category_severities: list[tuple[str, Severity]]) -> Action:
        """Resolve the final action across every category an input tripped."""
        if not category_severities:
            return Action.ALLOW
        actions = [self.action_for(category, severity) for category, severity in category_severities]
        return max(actions, key=lambda a: _ACTION_PRIORITY[a])


@cache
def get_policy_engine(name: str | None = None) -> PolicyEngine:
    """name=None (default) loads the root policy.yaml — unchanged, zero-config behavior.
    Pass a pack name (e.g. "strict", "healthcare", "enterprise") to load
    policies/<name>.yaml instead. Cached per name, same as before for the default case."""
    if name is None:
        return PolicyEngine(DEFAULT_POLICY_PATH)
    return PolicyEngine(POLICIES_DIR / f"{name}.yaml")
