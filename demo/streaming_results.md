# Streaming validation results

Full-buffer checking is ground truth here (it sees the entire response at once).
The question is how much windowed/streaming checking gives up relative to it.

| case | full-buffer | overlapping window | disjoint chunks |
|---|---|---|---|
| 0 | False | False | False |
| 1 | False | False | False |
| 2 | True | True | True |
| 3 | False | False | False |
| 4 | True | True | True |

- Full-buffer detections: 2/5
- Overlapping-window detections: 2/5 (0 missed relative to full-buffer)
- Disjoint-chunk detections: 2/5 (0 missed relative to full-buffer)

## Honest finding

No misses were observed for either windowing scheme on this test set, including two cases (2 and 4) deliberately constructed so a toxic phrase and a two-word PERSON name straddle a disjoint-chunk boundary exactly. Both the toxicity classifier and spaCy's NER turned out to be robust enough to flag a fragment alone (e.g. 'John' alone, or half a toxic phrase) without needing the other half.

This does NOT mean windowing is risk-free in general — it means the specific risk didn't materialize for these specific classifiers on natural-language content. The structural argument for overlap still holds analytically: a disjoint chunk boundary can, in principle, split a pattern that only scores confidently as a whole (this is provably true for exact-pattern regex entities like a credit card or SSN number, which cannot be matched at all if truncated mid-digit-sequence across chunks) — overlap guarantees every span up to `window_size` tokens is eventually seen intact by some window, which disjoint chunking does not guarantee. That guarantee just wasn't exercised by this particular test set.
