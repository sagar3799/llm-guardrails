"""Fails when README.md drifts from the code and committed eval results.

The README makes concrete, checkable claims (test count, file paths, headline eval
numbers, dataset sizes). Each of those has gone stale at least once during development
because the code moved and the README didn't — this makes that a test failure instead of
something a reader discovers. Compares two committed artifacts (README vs. results files),
so it's deterministic; regenerating an eval will fail this test until the README's quoted
numbers are updated to match, which is the point.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")

PATH_PATTERN = re.compile(r"(?<![\w:/.-])((?:[\w.-]+/)+[\w.-]+\.(?:py|md|yaml|json|svg))")


def _collected_test_count() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    assert match, f"couldn't parse pytest's collected count from:\n{result.stdout}"
    return int(match.group(1))


def test_readme_test_count_matches_collected_tests():
    claimed = re.search(r"\*\*(\d+)/(\d+) tests passing", README)
    assert claimed, "README no longer has a '**N/N tests passing' line to check"
    actual = _collected_test_count()
    assert int(claimed.group(1)) == int(claimed.group(2)) == actual, (
        f"README claims {claimed.group(0)!r} but pytest collects {actual} tests — "
        f"update the line in README.md"
    )


def test_every_path_mentioned_in_readme_exists():
    missing = sorted({p for p in PATH_PATTERN.findall(README) if not (ROOT / p).exists()})
    assert not missing, f"README references files that don't exist: {missing}"


def test_dataset_sizes_match_readme():
    for dataset in ("eval/redteam_cases.json", "eval/generated_outputs.json"):
        n = len(json.loads((ROOT / dataset).read_text(encoding="utf-8")))
        assert f"{n} cases" in README or f"{n} red-team cases" in README, (
            f"{dataset} has {n} cases but README never says '{n} cases'"
        )


def test_input_eval_headline_numbers_match_results_file():
    results = (ROOT / "eval/results.md").read_text(encoding="utf-8")
    for fraction in re.findall(r"\((\d+/\d+)\)", results.split("## Per-case")[0]):
        assert fraction in README, f"eval/results.md reports {fraction}, README doesn't"

    latency = re.search(r"mean ([\d.]+)ms, p95 ([\d.]+)ms", results)
    assert latency, "couldn't find latency line in eval/results.md"
    mean, p95 = latency.groups()
    assert f"mean {mean}ms, p95 {p95}ms" in README, (
        f"eval/results.md says mean {mean}ms, p95 {p95}ms but README quotes different "
        f"latency numbers — update the Phase 3 bullet"
    )


def test_output_eval_headline_numbers_match_results_file():
    results = (ROOT / "eval/output_results.md").read_text(encoding="utf-8")
    headline = results.split("## Per-case")[0]
    for fraction in re.findall(r"\((\d+/\d+)\)", headline):
        assert fraction in README, f"eval/output_results.md reports {fraction}, README doesn't"

    accuracy = re.search(r"Anonymization accuracy.*?: ([\d.]+)%", headline)
    assert accuracy, "couldn't find anonymization accuracy in eval/output_results.md"
    assert f"{float(accuracy.group(1)):.0f}%" in README


def test_policy_comparison_numbers_match_results_file():
    results = (ROOT / "eval/policy_comparison.md").read_text(encoding="utf-8")
    for policy in ("default", "strict"):
        row = next(line for line in results.splitlines() if line.startswith(f"| {policy} |"))
        attack_block, benign_block = re.findall(r"(\d+)% \(\d+/\d+\)", row)[-2:]
        for pct in (attack_block, benign_block):
            assert f"{pct}%" in README, (
                f"eval/policy_comparison.md has a {pct}% hard-block rate for '{policy}' "
                f"that README doesn't mention"
            )
