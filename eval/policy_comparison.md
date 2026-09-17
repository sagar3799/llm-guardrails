# Policy pack comparison

Same 25 red-team cases (eval/redteam_cases.json) run through each policy pack.
See the module docstring in run_policy_comparison.py for why two metrics are
reported instead of one.

| policy | catch rate | false-positive rate | attack hard-block rate | benign hard-block rate |
|---|---|---|---|---|
| default | 100% (15/15) | 40% (4/10) | 67% (10/15) | 30% (3/10) |
| strict | 100% (15/15) | 40% (4/10) | 100% (15/15) | 40% (4/10) |
| healthcare | 100% (15/15) | 40% (4/10) | 100% (15/15) | 40% (4/10) |
| enterprise | 100% (15/15) | 40% (4/10) | 67% (10/15) | 30% (3/10) |

## Reading this table

- **Catch rate and false-positive rate are flat across all four policies (100% / 40%).** This is expected, not a bug in the eval: policies only change WHICH action a triggered category gets, never whether detection fires. A policy-comparison table that only reported these two numbers would hide the real difference entirely — which is why hard-block rate is reported too.
- **Attack hard-block rate is where the real PII tradeoff shows up**: `default`/`enterprise` anonymize PII instead of blocking it, so their PII attack cases resolve to `anonymize`, not `block` — lowering their attack hard-block rate relative to `strict`/`healthcare`, which block PII outright.
- **Benign hard-block rate is the collateral-damage number**, and it has two distinct sources, not one: `borderline-01/02/04` hard-block under EVERY policy (they're injection-classifier false positives at HIGH severity, and all four policies block prompt_injection at HIGH regardless) — that's the policy-independent floor. `clean-03` (a fictional name tagged PERSON by spaCy — see eval/results.md) is the one case that differs BY policy: anonymized under `default`/`enterprise`, hard-blocked under `strict`/`healthcare`. That single case is the entire gap between the two pairs of policies in this column.
- These are the actual measured numbers from this run — read the table, not this paragraph, for what really happened.
