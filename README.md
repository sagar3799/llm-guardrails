# LLM Guardrails / Safety Middleware

Pluggable input/output guardrails for LLM applications — prompt injection, jailbreak,
PII, and toxicity detection, with policy-driven actions (block / anonymize / warn /
allow). Runs entirely on local, free classifiers: no LLM API call anywhere in the core
pipeline, so the guardrail never depends on the kind of system it's meant to constrain.

Full design, rationale, and the review history behind every decision here live in
[docs/buildplan.md](docs/buildplan.md).

```
Input Guardrails                          Output Guardrails
------------------                        -------------------
check_input(text)                         check_output(text)
  -> prompt injection detection             -> PII leak detection (Presidio)
  -> jailbreak pattern detection             -> toxicity detection (local classifier)
  -> PII in input (Presidio)

         \                                        /
          \                                      /
           v                                    v
              PolicyEngine (policy.yaml: category -> severity -> action)
                           |
                           v
              GuardResult(allowed, action, severity, risk_score,
                           sanitized_text, categories, matched_rules)
```

## Status: all phases built and tested

- **Phase 1** (input guardrails): prompt injection/jailbreak classifier (ONNX,
  `protectai/deberta-v3-base-prompt-injection-v2`) + regex fallback, PII detection
  (Presidio + spaCy `en_core_web_lg`), combined into `check_input()`. Verified to run
  fully offline (no network after first model download).
- **Phase 2** (output guardrails): toxicity classifier (ONNX, `unitary/toxic-bert`) +
  reused PII detector, combined into `check_output()` — same `GuardResult` shape as
  `check_input()`.
- **Phase 2.5** (policy engine): `policy.yaml` maps `category -> severity -> action`,
  so the same severity can mean `block` for one category and `anonymize` for another.
  PII is anonymized via `presidio-anonymizer` instead of hard-blocked. Conflicting
  categories on one input resolve via `BLOCK > ANONYMIZE > WARN > ALLOW`. Every non-ALLOW
  result logs a structured JSON explainability line (`action`, `severity`, `risk_score`,
  `categories`, `matched_rules`, `latency_ms`).
- **Phase 3** (red-team eval): 25 cases across prompt injection, jailbreak, PII, and
  clean/borderline controls — see [eval/results.md](eval/results.md). **Catch rate:
  100% (15/15 attacks correctly actioned). False-positive rate: 40% (4/10 benign
  cases flagged) — every single failure is individually root-caused in the results
  table**, not hidden: three are inherent limitations of the pretrained injection
  classifier's phrasing sensitivity, one is spaCy's NER tagging a fictional character
  name ("Romeo", "Juliet") as PERSON, same as it would a real name. **Latency
  (steady-state): mean 39.6ms, p95 164.9ms per `check_input()` call. Cold start
  (one-time model load per process): ~7.8s** — reported separately since it's not a
  per-request cost.
- **Phase 5** (streaming-aware validation): `StreamingGuard(window_size, stride)` runs
  toxicity/PII checks on an overlapping sliding window instead of buffering the full
  response — see [demo/streaming_results.md](demo/streaming_results.md). Two boundary-
  straddling test cases were deliberately constructed; neither produced a miss with
  either overlapping or disjoint windowing, because both classifiers turned out to be
  robust to fragment-level input on natural language. That's reported as the honest
  empirical result, alongside the analytical case for why overlap still matters in
  principle (it structurally guarantees full coverage of any span, which disjoint
  chunking does not — provably relevant for exact-pattern entities like credit card
  numbers, just not exercised by this test set).
- **Phase 4** (partial, by design): `examples/fastapi_app.py` — a single `POST /chat`
  endpoint wrapping a fake LLM call in `check_input()`/`check_output()`, smoke-tested
  end-to-end (clean / injection / PII cases). **CI and the LangGraph demo wrapper were
  deliberately skipped** — see "What's not here" below.
- **Pluggable detector interface**: `Detector` is a `Protocol` (not an ABC) — any object
  with a `check(text) -> DetectionSignal` method can be registered on a
  `GuardrailsEngine` via `register_detector(my_detector, stage="input"|"output")`, no
  subclassing required. The three built-ins are wrapped as plugins
  (`InjectionDetectorPlugin`, `PiiDetectorPlugin`, `ToxicityDetectorPlugin`) in
  `src/guardrails/builtin_detectors.py`, proving the interface with real detectors, not
  just a toy example. `check_input()`/`check_output()` in `middleware.py` are unaffected
  and remain the simple, zero-config entry point.
- **Versioned policy packs**: `policy.yaml` at the repo root stays the zero-config
  default; `policies/strict.yaml`, `policies/healthcare.yaml`, and
  `policies/enterprise.yaml` are named alternatives with genuinely different tradeoffs
  (e.g. `pii.low` is `warn` by default, `block` under `healthcare`, `block` under
  `strict`), selected via `get_policy_engine("healthcare")` or
  `GuardrailsEngine(policy_name="healthcare")`. The FastAPI demo exposes this directly —
  `POST /chat` with `{"message": "...", "policy": "healthcare"}` uses it.

## What's not here (and why)

- **CI**: a from-scratch build wouldn't have anything behind it worth discussing in an
  interview (see docs/buildplan.md, Revision 3) — it's optional polish, not part of the
  resume-ready claim, and isn't claimed anywhere in this README or the resume lines.
- **LangGraph demo wrapper**: deferred — it wraps a separate project's real code and
  wasn't needed to reach a complete, tested state here.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash; use .venv\Scripts\activate on cmd
pip install -e ".[dev]"
python -m spacy download en_core_web_lg
```

## Running tests

```bash
pytest -q
```

## Running the eval / demos

```bash
python eval/run_redteam.py            # writes eval/results.md
python demo/streaming_validation.py   # writes demo/streaming_results.md
uvicorn examples.fastapi_app:app --reload   # then POST to /chat
```
