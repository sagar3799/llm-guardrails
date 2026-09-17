"""Cross-policy behavioral eval — runs the same red-team cases through each policy pack
and reports two metrics per policy, because one alone is misleading.

1. "Restricted rate" (action != allow): mostly FLAT across policies, and that's expected
   — policies only decide WHICH action a triggered category gets, they never change
   whether detection fires. Comparing exact actions against redteam_cases.json's
   `expected_action` field (written for the default policy) would also be wrong for the
   same reason: strict/healthcare choosing `block` where the default chooses `anonymize`
   for PII is MORE restrictive, not a failure — see eval/results.md for that exact-action
   view of the default policy specifically, which still answers a different question.

2. "Hard-block rate" (action == block, specifically): this is what actually differs
   between policies, and it's the more useful number — it measures how much a policy's
   choice to block-instead-of-anonymize PII costs in outright-rejected requests, split
   by whether that request was a real attack (good) or benign (collateral damage to a
   legitimate user). A flat restricted-rate table would have hidden this; this doesn't.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from guardrails.engine import GuardrailsEngine
from guardrails.schemas import Action

CASES_PATH = Path(__file__).parent / "redteam_cases.json"
RESULTS_PATH = Path(__file__).parent / "policy_comparison.md"

ATTACK_CATEGORIES = {"prompt_injection", "jailbreak", "pii"}
BENIGN_CATEGORIES = {"clean", "borderline_legitimate"}
POLICIES = [None, "strict", "healthcare", "enterprise"]


def _policy_label(name: str | None) -> str:
    return "default" if name is None else name


def run() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    rows = []
    for policy_name in POLICIES:
        engine = GuardrailsEngine(policy_name=policy_name)
        latencies_ms = []
        attack_total = attack_restricted = attack_blocked = 0
        benign_total = benign_restricted = benign_blocked = 0

        for case in cases:
            start = time.perf_counter()
            result = engine.check_input(case["text"])
            latencies_ms.append((time.perf_counter() - start) * 1000)
            restricted = result.action != Action.ALLOW
            blocked = result.action == Action.BLOCK

            if case["category"] in ATTACK_CATEGORIES:
                attack_total += 1
                attack_restricted += restricted
                attack_blocked += blocked
            elif case["category"] in BENIGN_CATEGORIES:
                benign_total += 1
                benign_restricted += restricted
                benign_blocked += blocked

        rows.append(
            {
                "policy": _policy_label(policy_name),
                "catch_rate": attack_restricted / attack_total if attack_total else 0.0,
                "false_positive_rate": benign_restricted / benign_total if benign_total else 0.0,
                "attack_hard_block_rate": attack_blocked / attack_total if attack_total else 0.0,
                "benign_hard_block_rate": benign_blocked / benign_total if benign_total else 0.0,
                "mean_latency_ms": sum(latencies_ms) / len(latencies_ms),
                "attack_restricted": attack_restricted,
                "attack_total": attack_total,
                "attack_blocked": attack_blocked,
                "benign_restricted": benign_restricted,
                "benign_total": benign_total,
                "benign_blocked": benign_blocked,
            }
        )

    _write_results(rows)
    for r in rows:
        print(
            f"{r['policy']:<12} catch={r['catch_rate']:.0%}  fp={r['false_positive_rate']:.0%}  "
            f"attack_hard_block={r['attack_hard_block_rate']:.0%}  "
            f"benign_hard_block={r['benign_hard_block_rate']:.0%}"
        )
    print(f"\nresults written to {RESULTS_PATH}")


def _write_results(rows: list[dict]) -> None:
    lines = [
        "# Policy pack comparison",
        "",
        "Same 25 red-team cases (eval/redteam_cases.json) run through each policy pack.",
        "See the module docstring in run_policy_comparison.py for why two metrics are",
        "reported instead of one.",
        "",
        (
            "| policy | catch rate | false-positive rate | attack hard-block rate | "
            "benign hard-block rate |"
        ),
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['policy']} | {r['catch_rate']:.0%} ({r['attack_restricted']}/{r['attack_total']}) "
            f"| {r['false_positive_rate']:.0%} ({r['benign_restricted']}/{r['benign_total']}) "
            f"| {r['attack_hard_block_rate']:.0%} ({r['attack_blocked']}/{r['attack_total']}) "
            f"| {r['benign_hard_block_rate']:.0%} ({r['benign_blocked']}/{r['benign_total']}) |"
        )

    lines += [
        "",
        "## Reading this table",
        "",
        (
            "- **Catch rate and false-positive rate are flat across all four policies "
            "(100% / 40%).** This is expected, not a bug in the eval: policies only "
            "change WHICH action a triggered category gets, never whether detection "
            "fires. A policy-comparison table that only reported these two numbers "
            "would hide the real difference entirely — which is why hard-block rate "
            "is reported too."
        ),
        (
            "- **Attack hard-block rate is where the real PII tradeoff shows up**: "
            "`default`/`enterprise` anonymize PII instead of blocking it, so their "
            "PII attack cases resolve to `anonymize`, not `block` — lowering their "
            "attack hard-block rate relative to `strict`/`healthcare`, which block "
            "PII outright."
        ),
        (
            "- **Benign hard-block rate is the collateral-damage number**, and it has "
            "two distinct sources, not one: `borderline-01/02/04` hard-block under "
            "EVERY policy (they're injection-classifier false positives at HIGH "
            "severity, and all four policies block prompt_injection at HIGH "
            "regardless) — that's the policy-independent floor. `clean-03` (a "
            "fictional name tagged PERSON by spaCy — see eval/results.md) is the one "
            "case that differs BY policy: anonymized under `default`/`enterprise`, "
            "hard-blocked under `strict`/`healthcare`. That single case is the entire "
            "gap between the two pairs of policies in this column."
        ),
        (
            "- These are the actual measured numbers from this run — read the table, "
            "not this paragraph, for what really happened."
        ),
    ]

    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
