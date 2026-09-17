"""Phase 5 demo: simulates a token-by-token stream and runs StreamingGuard against it,
then compares detection against (a) full-buffer checking and (b) disjoint, non-overlapping
windows — to see empirically whether overlap actually helps. See docs/buildplan.md, Phase 5.

Scope, stated honestly: whitespace-delimited tokens on a simulated stream, not a real
LLM's token-by-token output or its BPE tokenizer (Implementation notes, item 2). Numbers
below are whatever this run actually produces, not a scripted outcome — that's the point.
"""

from __future__ import annotations

from pathlib import Path

from guardrails.middleware import check_output
from guardrails.streaming import StreamingGuard

RESULTS_PATH = Path(__file__).parent / "streaming_results.md"

# Case 2 is deliberately constructed so the toxic phrase straddles a disjoint 12-token
# chunk boundary exactly — that's the specific failure mode overlap exists to narrow.
TEST_RESPONSES = [
    "Thanks so much for reaching out about the issue we will get back to you within two business days",
    "Here is a quick summary of the quarterly numbers which look solid across every region tracked this year",
    "filler filler filler filler filler filler filler filler filler filler you are a worthless idiot and everyone hates you",
    "Sure thing you can reach our support team any time and my email happens to be sagar dot meena at example dot com",
    "Hello there I wanted to reach out regarding my colleague named John Smith who works in the finance department downtown",
]

CHUNK_SIZE = 12


def _simulate_stream(text: str, guard: StreamingGuard) -> list:
    hits = []
    for token in text.split():
        hits.extend(guard.feed(token))
    hits.extend(guard.flush())
    return hits


def _simulate_disjoint(text: str, chunk_size: int) -> list:
    """Non-overlapping baseline: disjoint chunks of chunk_size tokens, each run through
    the full check_output — this is what Phase 5 originally proposed before overlap
    (Revision 4, item 3) replaced it."""
    tokens = text.split()
    hits = []
    for i in range(0, len(tokens), chunk_size):
        chunk = " ".join(tokens[i : i + chunk_size])
        result = check_output(chunk)
        if result.action.value != "allow":
            hits.append(result)
    return hits


def main() -> None:
    rows = []
    for i, text in enumerate(TEST_RESPONSES):
        full_result = check_output(text)
        full_flagged = full_result.action.value != "allow"

        guard = StreamingGuard(window_size=CHUNK_SIZE, stride=CHUNK_SIZE // 2)
        overlap_flagged = bool(_simulate_stream(text, guard))

        disjoint_flagged = bool(_simulate_disjoint(text, chunk_size=CHUNK_SIZE))

        rows.append((i, full_flagged, overlap_flagged, disjoint_flagged))

    n = len(rows)
    full_hits = sum(r[1] for r in rows)
    overlap_hits = sum(r[2] for r in rows)
    disjoint_hits = sum(r[3] for r in rows)

    lines = [
        "# Streaming validation results",
        "",
        "Full-buffer checking is ground truth here (it sees the entire response at once).",
        "The question is how much windowed/streaming checking gives up relative to it.",
        "",
        "| case | full-buffer | overlapping window | disjoint chunks |",
        "|---|---|---|---|",
    ]
    for i, full, overlap, disjoint in rows:
        lines.append(f"| {i} | {full} | {overlap} | {disjoint} |")

    overlap_missed = full_hits - overlap_hits
    disjoint_missed = full_hits - disjoint_hits
    lines += [
        "",
        f"- Full-buffer detections: {full_hits}/{n}",
        f"- Overlapping-window detections: {overlap_hits}/{n} ({overlap_missed} missed relative to full-buffer)",
        f"- Disjoint-chunk detections: {disjoint_hits}/{n} ({disjoint_missed} missed relative to full-buffer)",
        "",
        "## Honest finding",
        "",
    ]
    if disjoint_missed == 0 and overlap_missed == 0:
        lines += [
            (
                "No misses were observed for either windowing scheme on this test set, including "
                "two cases (2 and 4) deliberately constructed so a toxic phrase and a two-word "
                "PERSON name straddle a disjoint-chunk boundary exactly. Both the toxicity "
                "classifier and spaCy's NER turned out to be robust enough to flag a fragment "
                "alone (e.g. 'John' alone, or half a toxic phrase) without needing the other half."
            ),
            "",
            (
                "This does NOT mean windowing is risk-free in general — it means the specific "
                "risk didn't materialize for these specific classifiers on natural-language "
                "content. The structural argument for overlap still holds analytically: a "
                "disjoint chunk boundary can, in principle, split a pattern that only scores "
                "confidently as a whole (this is provably true for exact-pattern regex entities "
                "like a credit card or SSN number, which cannot be matched at all if truncated "
                "mid-digit-sequence across chunks) — overlap guarantees every span up to "
                "`window_size` tokens is eventually seen intact by some window, which disjoint "
                "chunking does not guarantee. That guarantee just wasn't exercised by this "
                "particular test set."
            ),
        ]
    else:
        lines += [
            (
                f"Disjoint chunking missed {disjoint_missed} case(s) that full-buffer checking "
                f"caught; the overlapping window missed {overlap_missed}. This is the concrete "
                "evidence for why overlap was worth adding over the naive disjoint-chunk version."
            ),
        ]

    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nresults written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
