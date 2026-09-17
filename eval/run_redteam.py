"""Red-team eval harness: runs every case in redteam_cases.json through check_input(),
scores the actual action against the expected one, and writes eval/results.md.

Reports catch rate, false-positive rate, AND mean/p95 latency — see
docs/buildplan.md, Phase 3 and Revision 2 item 4. Attack categories (prompt_injection,
jailbreak, pii) roll up into catch rate; non-attack categories (clean, borderline)
roll up into false-positive rate, since a guardrail's real cost is legitimate requests
it wrongly flags, not just how many attacks it lets through.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from guardrails.middleware import check_input

CASES_PATH = Path(__file__).parent / "redteam_cases.json"
RESULTS_PATH = Path(__file__).parent / "results.md"

ATTACK_CATEGORIES = {"prompt_injection", "jailbreak", "pii"}
BENIGN_CATEGORIES = {"clean", "borderline_legitimate"}


def run() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    # Model loading (first call per process) is a one-time cost, not representative of
    # steady-state per-request latency — warm up here so it doesn't skew mean/p95 below.
    warmup_start = time.perf_counter()
    check_input("warmup call to trigger model loading")
    cold_start_ms = (time.perf_counter() - warmup_start) * 1000

    rows = []
    latencies_ms = []

    for case in cases:
        start = time.perf_counter()
        result = check_input(case["text"])
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed_ms)

        actual_action = result.action.value
        passed = actual_action == case["expected_action"]

        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected": case["expected_action"],
                "actual": actual_action,
                "passed": passed,
                "latency_ms": elapsed_ms,
                "note": case.get("note", ""),
            }
        )

    attack_rows = [r for r in rows if r["category"] in ATTACK_CATEGORIES]
    benign_rows = [r for r in rows if r["category"] in BENIGN_CATEGORIES]

    catch_rate = sum(r["passed"] for r in attack_rows) / len(attack_rows) if attack_rows else 0.0
    false_positive_rate = (
        sum(not r["passed"] for r in benign_rows) / len(benign_rows) if benign_rows else 0.0
    )

    mean_latency = statistics.mean(latencies_ms)
    p95_latency = statistics.quantiles(latencies_ms, n=100)[94] if len(latencies_ms) >= 2 else latencies_ms[0]

    _write_results(rows, attack_rows, benign_rows, catch_rate, false_positive_rate, mean_latency, p95_latency, cold_start_ms)
    print(f"catch_rate={catch_rate:.2%}  false_positive_rate={false_positive_rate:.2%}  "
          f"mean_latency={mean_latency:.1f}ms  p95_latency={p95_latency:.1f}ms  cold_start={cold_start_ms:.1f}ms")
    print(f"results written to {RESULTS_PATH}")


def _write_results(rows, attack_rows, benign_rows, catch_rate, false_positive_rate, mean_latency, p95_latency, cold_start_ms) -> None:
    lines = [
        "# Red-team evaluation results",
        "",
        f"- **Catch rate** (attacks correctly actioned): {catch_rate:.2%} ({sum(r['passed'] for r in attack_rows)}/{len(attack_rows)})",
        (
            f"- **False-positive rate** (benign inputs incorrectly flagged): {false_positive_rate:.2%} "
            f"({sum(not r['passed'] for r in benign_rows)}/{len(benign_rows)})"
        ),
        (
            f"- **Latency (steady-state)**: mean {mean_latency:.1f}ms, p95 {p95_latency:.1f}ms "
            "(check_input, per case, after model warmup)"
        ),
        (
            f"- **Cold start** (first call in a process, includes model loading): {cold_start_ms:.1f}ms — "
            "a one-time cost per process, not a per-request cost; excluded from the steady-state numbers above."
        ),
        "",
        "## Per-case results",
        "",
        "| id | category | expected | actual | pass | latency (ms) | note |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        status = "✅" if r["passed"] else "❌"
        lines.append(
            f"| {r['id']} | {r['category']} | {r['expected']} | {r['actual']} | {status} | "
            f"{r['latency_ms']:.1f} | {r['note']} |"
        )

    failures = [r for r in rows if not r["passed"]]
    lines += ["", "## Known weak spots"]
    if failures:
        for r in failures:
            reason = r["note"] or "no note recorded"
            lines.append(f"- **{r['id']}** ({r['category']}): expected `{r['expected']}`, got `{r['actual']}` — {reason}")
    else:
        lines.append("- None in this run.")

    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
