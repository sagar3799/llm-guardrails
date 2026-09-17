# Project: LLM Guardrails / Safety Middleware

**New repo, separate from all three existing projects.** Different purpose, different codebase.

**What this proves that Projects 1-3 don't:** Project 1 proves you can build an agent.
Project 2 proves you can build a tool protocol. Project 3 proves you can ship and observe one.
None of them constrain what the system will actually do or say in real time — evals check
quality *after the fact*, guardrails act *in the moment*. That's the gap real job postings
named directly: "ensure clarity, grounding, safety... minimize hallucinations," and hiring
guides for this exact role calling out "implemented guardrails" as a specific differentiator.

**Resume lines (two, single-line, matching your current format):**
```
Built a pluggable LLM guardrails middleware separating model-scored severity from policy-driven actions (block, anonymize, warn) for prompt injection, jailbreaks, and PII leakage using fully local classifiers
Validated with a red-team test suite measuring detection rate, false-positive rate, and p95 latency, with structured explainability logging for every blocked request
```
*(CI claim removed — see Revision 3, item 1. Don't re-add "with CI on every push" unless CI is actually shipped. Severity/explainability framing added in Revision 5.)*

**Time: ~1-1.5 weeks of evenings**, same size class as the MCP server, not another Project 1.

---

## Revision 2 — review changelog

Four changes from the original plan, each tagged inline below at the spot it touches
(search for "Revision 2, item N"). Format is **Before → After**, **Why**, **Effect**.

**1. Prompt-injection / toxicity classifiers: stopped overclaiming "no-PyTorch."**
- Before: described as "same lightweight, no-PyTorch pattern as `fastembed`."
- Why: `fastembed` ships models with pre-converted ONNX weights on the hub. Neither
  `protectai/deberta-v3-base-prompt-injection-v2` nor `unitary/toxic-bert` does, as far as
  can be confirmed — getting either into `onnxruntime` form likely needs a one-time
  `optimum` conversion pass, which pulls in PyTorch as a build-time dependency.
- Effect: no architecture change. The README now says PyTorch is a conversion-time
  dependency only, not a runtime one — accurate instead of overstated. If a truly
  PyTorch-free setup matters more than the exact model, check the hub for an already-ONNX
  checkpoint before Phase 1, or fall back to plain `transformers` + `onnxruntime` at
  inference time without a local conversion step.

**2. PII detector: pinned the spaCy model instead of leaving it implicit.**
- Before: "Microsoft Presidio... detects emails, phone numbers, names, credit card
  numbers, etc." with no model specified.
- Why: Presidio needs spaCy for NER — that's specifically how it catches *names*, not the
  regex-matchable fields. `en_core_web_lg` (~560MB) has materially better name recall than
  `en_core_web_sm`, but is a much heavier download, which cuts against the "zero setup"
  framing carried over from the MCP server project.
- Effect: plan now calls for `en_core_web_lg` and says so honestly in the README (download
  size stated up front). If setup weight matters more than name-recall accuracy, swap to
  `en_core_web_sm` instead — but decide explicitly and note the tradeoff, rather than
  leaving it to whatever `pip install` happens to pull.

**3. `GuardResult` schema: `category: str` → `categories: list[str]`.**
- Before: `GuardResult(allowed: bool, reasons: list[str], category: str)`.
- Why: a single input can trip more than one check at once — e.g. a jailbreak attempt that
  also contains an email address. A singular `category` field can't represent that without
  an awkward "pick the worse one" rule baked into the pipeline.
- Effect: `categories` becomes a list so multi-trigger cases are representable, and each
  entry in `reasons` can be paired with the category it came from. Every later reference to
  `category` in this doc should now be read as `categories`.

**4. Phase 3: added latency measurement alongside catch rate / false-positive rate.**
- Before: results table tracked only catch rate and false-positive rate.
- Why: this middleware sits in the request path — "does this add noticeable latency"
  is a near-guaranteed question in any interview about this project, and `run_redteam.py`
  is already timing every case through the pipeline, so capturing it costs almost nothing.
- Effect: `run_redteam.py` also records mean/p95 wall-clock time per check; the results
  table and README report it as a third headline number, alongside catch rate and
  false-positive rate. New Phase 3 checkpoint item added below.

---

## Revision 3 — review changelog (after CPT + Gemini review)

Three changes, incorporating what survived scrutiny from two external reviews. Same
format as Revision 2: **Before → After**, **Why**, **Effect**.

**1. Resume bullet: dropped the CI claim instead of rushing CI to make it true.**
- Before: bullet claimed "CI running lint and tests on every push"; Revision 2 already
  flagged this contradicted "Phase 3 is the finish line," and offered two fixes —
  build minimal CI now, or drop the claim until it's real.
- Why (your call): a 20-minute CI badge has nothing behind it worth discussing in an
  interview. Better to spend the same hours on something defensible than on a claim
  that's technically true but empty the moment someone asks a follow-up question.
- Effect: resume bullets no longer mention CI. CI stays in Phase 4 as genuinely optional
  — build it only if everything else is done and you want the badge, and don't put it on
  a CV until it exists in the repo.

**2. Merged CPT's policy engine with Gemini's redaction/Action-enum idea into one design.**
- Before: `check_input()`/`check_output()` only returned `allowed: bool` + `reasons` +
  `categories`. Any PII hit — even one email address in an otherwise legitimate prompt —
  hard-blocked the whole request.
- Why: two independent reviews converged on the same gap from different angles. CPT's
  fix was a `policy.yaml` mapping category → action (block/redact/warn). Gemini's fix was
  an `Action` enum plus Presidio's own `presidio-anonymizer` companion package to replace
  PII with placeholders instead of rejecting the prompt outright. These aren't two
  features, they're the same fix described twice — worth building once, properly.
- Effect: new **Phase 2.5** below. `GuardResult` gains `action: Action` (`BLOCK` /
  `ANONYMIZE` / `WARN` / `ALLOW`) and `sanitized_text: str | None`. A `policy.yaml`
  (category → action) is read by a small `PolicyEngine` class the middleware consults
  after detection. PII hits route through `presidio-anonymizer` (new dependency,
  install alongside `presidio-analyzer`) and come back with placeholders like
  `<EMAIL_ADDRESS>` instead of a flat rejection. Phase 3's red-team cases now need an
  expected *action*, not just a pass/fail verdict — updated below.

**3. Streaming/TTFT limitation: built a real (simplified) demo instead of a README caveat.**
- Before: no mention of streaming; `check_output()` implicitly assumes the full response
  is already buffered before any check runs.
- Why: Gemini's underlying observation is correct — buffering the whole response before
  scanning it defeats time-to-first-token in any real streaming LLM app. But Gemini's own
  proposed "fix" was just a sentence in the README acknowledging the limitation, which is
  the same category of shortcut as the rejected 20-minute CI: cheap to write, nothing to
  show. Since time isn't the constraint here, a working (if simplified) version is more
  defensible than a description of one.
- Effect: new **Phase 5** below (not gated behind "if time allows" — treat it as the
  project's differentiator). A `demo/streaming_validation.py` simulates token-by-token
  generation and runs the toxicity/PII checks on a sliding window every N tokens instead
  of waiting for the full response. Report the real tradeoff honestly: chunked checks
  have a higher false-negative rate near chunk boundaries than full-buffer checks — state
  that number the same way you state false-positive rate and latency elsewhere.

*(Discarded without action: CPT's "don't build" list — LLM-based safety judge,
fine-tuning your own detector, OCR/image moderation, voice input safety — is sound but
just restates scope discipline already implicit in this doc; written out explicitly under
"What NOT to do" below. The GuardRailX rename and Gemini's praise section were
branding/flattery with no effect on the plan — skipped.)*

---

## Revision 4 — review changelog (after GPT + Gemini follow-up review)

Three more changes. GPT's removal list duplicated CPT's from Revision 3 — already
covered under "What NOT to do," no new action there.

**1. Structured explainability output on every non-ALLOW action.**
- Before: `GuardResult.reasons` was free-text like `"blocked: prompt_injection,
  confidence 0.94"` — human-readable, not machine-parseable, no dedicated confidence or
  rule-identifier field.
- Why: GPT's suggestion is genuinely useful and nearly free — everything it needs
  (categories, timing) already exists elsewhere in the design; it just needed the
  confidence score and the specific rule that fired pulled out of a string and into
  real fields. A structured block-report log line is a concrete, show-in-an-interview
  artifact, unlike a vague "it's explainable" claim.
- Effect: `GuardResult` gains `risk_score: float | None` (max confidence across
  triggered checks) and `matched_rules: list[str]` (e.g. `"injection_classifier"`,
  `"regex:ignore_previous_instructions"`). The middleware logs a structured JSON line
  (`action`, `risk_score`, `categories`, `matched_rules`, `latency_ms`) whenever the
  action isn't `ALLOW`. Folded into Phase 2.5 — no new phase needed.

**2. `PolicyEngine` gets an explicit conflict-resolution rule.**
- Before: `PolicyEngine.decide(categories) -> Action` was described only as "a dict
  lookup with a default" — undefined behavior when one input trips categories that map
  to *different* actions (e.g. `pii: anonymize` and `prompt_injection: block` on the
  same input).
- Why: this was a real latent bug, not just a documentation gap — without an explicit
  rule, whichever category the code happens to check last silently wins, which is
  nondeterministic behavior in a safety-critical path.
- Effect: `PolicyEngine` resolves conflicts by a fixed priority order —
  `BLOCK > ANONYMIZE > WARN > ALLOW` (most-restrictive-wins). Added as an explicit Phase
  2.5 checkpoint case below.

**3. Streaming demo uses overlapping sliding windows, not disjoint chunks.**
- Before: Phase 5 described checking "a sliding window every N tokens" without
  specifying overlap.
- Why: non-overlapping windows guarantee that some multi-token attack phrases or
  split PII entities (an email address cut across a chunk boundary) are never scored as
  a whole — a real, predictable failure mode, not an edge case. Overlapping windows is
  the standard fix from NLP/signal-processing windowing, and costs about the same amount
  of code.
- Effect: `streaming_validation.py` uses a window size (e.g. 40 tokens) evaluated every
  stride (e.g. 20 tokens) instead of disjoint one-shot chunks. README names this
  explicitly as "overlapping windowing," since that's the detail that signals it was
  actually thought through rather than the naive first draft.

---

## Revision 5 — review changelog (final)

**This is the last review pass — the plan is now locked for build.** Two more additions
kept, one repackaging kept, three build-phase notes recorded (not structural changes).

**1. Severity, separate from Action.**
- Before: `PolicyEngine` mapped category directly to an action, with no independent
  notion of how severe a given hit actually was.
- Why: GPT's framing is the right one — *severity is what the model measured, action is
  what the business decided to do about it.* Collapsing them into one field means you
  can't answer "how confident was this block?" without re-deriving it from `risk_score`
  by hand, and you can't let two categories share a severity scale independently of
  what each one's policy happens to say.
- Effect: `GuardResult` gains `severity: Severity` (`HIGH` / `MEDIUM` / `LOW`), derived
  from `risk_score` via fixed thresholds (e.g. ≥0.8 HIGH, ≥0.5 MEDIUM, else LOW).
  `policy.yaml` is restructured from a flat `category -> action` map to a nested
  `category -> {severity -> action}` map (below, Phase 2.5), so business policy can
  still differ by category (e.g. treat HIGH-severity PII differently from HIGH-severity
  injection) while severity itself stays a pure model output. The `BLOCK > ANONYMIZE >
  WARN > ALLOW` conflict-resolution rule from Revision 4 is unchanged and still applies
  across categories.

**2. Added a FastAPI demo endpoint — one file, not a rewrite.**
- Before: only a CLI/script-based demo (`wrap_langgraph_agent.py`, `streaming_validation.py`).
- Why: GPT's point stands — a `POST /chat` endpoint that visibly intercepts a request is
  far easier for someone skimming your portfolio to understand in ten seconds than a
  script they'd have to run and read to make sense of. It's also genuinely one file, not
  scope creep — the whole point is that FastAPI never becomes the project.
- Effect: `examples/fastapi_app.py` added to Phase 4 — one endpoint, a fake/canned LLM
  call, guardrails wrapped around it. Nothing else in the repo depends on it.

**3. Phase 5 repackaged around a reusable `StreamingGuard` class instead of a bare script.**
- Before: the sliding-window logic lived directly inside `demo/streaming_validation.py`
  as procedural code.
- Why: GPT's repackaging point is correct and cheap to apply — the exact same
  overlapping-window logic, exposed as `StreamingGuard(window_size=40, stride=20)` with a
  `.feed(token)` method, reads as a piece of the library instead of a one-off script.
  Same logic, better API, more reusable, and more impressive to hand someone as `pip
  install`-able code.
- Effect: the windowing logic moves into `src/guardrails/streaming.py` as a
  `StreamingGuard` class; `demo/streaming_validation.py` becomes a thin script that feeds
  a simulated token generator into it and prints/logs the results. Phase 5's goals and
  checkpoint are otherwise unchanged.

**Recorded as build-phase notes, not plan changes (Gemini's follow-up — no structural
edits needed, per Gemini's own framing that the plan is already complete):**
see the new "Implementation notes" section at the end of this document for: the
Presidio+ONNX memory footprint and a lite-mode fallback for constrained deployments,
the word-splitting-vs-BPE caveat for the streaming demo, and the one-way (non-reversible)
nature of PII anonymization.

---

## 0. One deliberate design choice, made up front

**No LLM API calls anywhere in this project — everything runs on local, free classifiers.**

This is not a limitation, it's the correct engineering choice, and worth stating plainly in
your README: a guardrail that itself depends on an API call is slower, costs money per check,
and — worse — depends on the very kind of system it's supposed to be constraining. Real
guardrail systems (Llama Guard, NeMo Guardrails, Presidio) lean heavily on small, fast, local
classifiers for exactly this reason. It also keeps this consistent with your existing
"works with zero setup" principle from the MCP server, and sidesteps the exact problem that
got the activity-analyzer idea dropped from Project 2 (a tool that needs an LLM key just to
do its basic job).

---

## 1. Architecture

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
              GuardResult(allowed: bool, reasons: list[str], categories: list[str],
                          action: Action, sanitized_text: str | None,
                          risk_score: float | None, matched_rules: list[str],
                          severity: Severity)
              # ← Revision 2, item 3: `categories` was a singular `category: str`
              # ← Revision 3, item 2: `action` + `sanitized_text` are new (Phase 2.5)
              # ← Revision 4, item 1: `risk_score` + `matched_rules` are new (Phase 2.5)
              # ← Revision 5, item 1: `severity` is new — model output, independent of `action`
```

Two independent, composable pieces — input checks run before a prompt reaches an LLM, output
checks run before a response reaches a user. Each check returns a typed result (Pydantic,
same pattern as your other projects), not just True/False, so the caller knows *why* something
was blocked.

**Libraries, all free and local:**
- **Prompt injection / jailbreak detection**: a small, purpose-built classifier model
  (`protectai/deberta-v3-base-prompt-injection-v2` on Hugging Face, runs via `onnxruntime`.
  PyTorch/`optimum` is needed once, at conversion time, to produce the ONNX weights — not a
  runtime dependency. See Revision 2, item 1.) plus a regex/keyword fallback list for
  well-known jailbreak phrasings as a second signal.
- **PII detection**: **Microsoft Presidio** (open source, industry-standard, free, fully
  local) — detects emails, phone numbers, names, credit card numbers, etc. in both input and
  output text. Names/entities rely on spaCy `en_core_web_lg` (heavier download, better name
  recall than `en_core_web_sm` — state the size honestly in the README). See Revision 2,
  item 2.
- **Toxicity detection**: a small local classifier (`unitary/toxic-bert` or similar via
  `transformers` + `onnxruntime`) for output-side content checks. Same conversion-time
  PyTorch caveat as the injection classifier above.

---

## 2. Project structure

```
llm-guardrails/
  src/guardrails/
    schemas.py           # GuardResult, Action enum, Severity enum, Verdict models (Pydantic)
    injection_detector.py    # classifier + regex fallback
    pii_detector.py           # Presidio analyzer wrapper (detection)
    pii_anonymizer.py         # Presidio anonymizer wrapper (redaction) — Phase 2.5
    toxicity_detector.py      # local classifier wrapper
    policy.py                 # PolicyEngine: reads policy.yaml, category+severity -> action — Phase 2.5
    streaming.py              # StreamingGuard(window_size, stride).feed(token) — Phase 5, Revision 5 item 3
    pipeline.py               # orchestrates checks, combines results, applies policy
    middleware.py             # the pluggable wrapper: check_input(), check_output()
  policy.yaml                 # category -> {severity -> action} config — Phase 2.5, Revision 5 item 1
  examples/
    fastapi_app.py           # POST /chat demo: guardrails wrapping a fake LLM call — Phase 4, Revision 5 item 2
  demo/
    wrap_langgraph_agent.py  # optional: wraps your Project 1 agent as a live example
    streaming_validation.py  # thin script: feeds a simulated token stream into StreamingGuard
  eval/
    redteam_cases.json    # categorized attack prompts with expected action (not just verdict)
    run_redteam.py         # scores expected action per category, times each check, writes results.md
  tests/
    test_injection_detector.py
    test_pii_detector.py
    test_pii_anonymizer.py
    test_toxicity_detector.py
    test_policy.py
    test_streaming.py
    test_pipeline.py
  pyproject.toml
  README.md
```

---

## Phase 1: Input guardrails — ship this fully before touching output checks

**Day 1-2: Prompt injection + jailbreak detection, standalone, no pipeline yet.**
Get the classifier model loading and scoring real strings correctly on its own — test it
against a handful of obvious injection attempts ("ignore previous instructions...") and
obvious non-attempts ("what's the weather today"), before building anything around it.

**Day 2-3: PII detection via Presidio, standalone.**
Same isolation principle as always: test Presidio directly against sample text containing an
email, a phone number, a name — confirm it flags them — before wiring it into anything else.

**Day 3-4: Combine into `check_input()`.**
One function, takes text, returns a `GuardResult` combining both checks with clear per-category
reasons ("blocked: prompt_injection, confidence 0.94" / "flagged: pii_detected, type=EMAIL").

### Phase 1 checkpoint
- [ ] `check_input()` correctly blocks at least 3 distinct real injection/jailbreak attempts
- [ ] `check_input()` correctly flags PII in sample text and does NOT flag clean text
- [ ] Both classifiers run fully locally — confirm by disconnecting network and re-running

---

## Phase 2: Output guardrails

**Day 5: Toxicity detection, standalone**, same test-alone-first pattern.

**Day 5-6: PII leak detection on output** — reuse the same Presidio wrapper from Phase 1, applied
to LLM-generated text instead of user input (the same detector, different call site — don't
duplicate the code).

**Day 6: Combine into `check_output()`**, same `GuardResult` shape as `check_input()` for
consistency.

### Phase 2 checkpoint
- [ ] `check_output()` flags toxic content and leaked PII independently
- [ ] Both `check_input()` and `check_output()` return the same result type — a caller can
      handle both uniformly

---

## Phase 2.5: Policy engine + PII redaction (new — Revision 3, item 2)

This is what turns "a pile of detectors" into "middleware with a decision layer" — the
single addition both external reviews landed on independently.

**Day 7: `Severity` + `risk_score` thresholds.**
`risk_score` (max classifier confidence across whatever triggered) maps to `Severity` via
fixed thresholds — e.g. `>= 0.8` → `HIGH`, `>= 0.5` → `MEDIUM`, else `LOW`. This is a pure
model-output computation with no policy config involved (Revision 5, item 1) — keep it
that way, so severity always means the same thing regardless of what a company's policy
does with it.

**Day 7-8: `policy.yaml` + `PolicyEngine`, keyed by category *and* severity.**
```yaml
prompt_injection:
  HIGH: block
  MEDIUM: block
  LOW: warn
jailbreak:
  HIGH: block
  MEDIUM: block
  LOW: warn
pii:
  HIGH: block
  MEDIUM: anonymize
  LOW: warn
toxicity:
  HIGH: block
  MEDIUM: warn
  LOW: allow
```
`PolicyEngine.decide(categories: list[str], severity_by_category: dict) -> Action` reads
this nested map and returns the action for a `GuardResult`. This is the concrete
"severity is model output, action is business policy" separation — the same severity can
map to a different action depending on category (a `HIGH` toxicity hit only warns; a
`HIGH` PII hit blocks outright), and a company can retune the whole policy by editing YAML,
no code changes. **When an input trips more than one category with different resulting
actions, resolve deterministically by priority: `BLOCK > ANONYMIZE > WARN > ALLOW` —
most-restrictive wins, always** (Revision 4, item 2). Don't let this fall out of
iteration order by accident.

**Day 8-9: PII anonymization via `presidio-anonymizer`.**
Add the companion package to `presidio-analyzer` (already in use since Phase 1). When
`PolicyEngine` returns `ANONYMIZE` for a PII hit, run the anonymizer and populate
`sanitized_text` with entities replaced by placeholders (e.g. `<EMAIL_ADDRESS>`) instead
of setting `allowed: false`. Injection/jailbreak hits still hard-block per policy.

**Day 9: Wire `action`, `severity`, `sanitized_text`, `risk_score`, and `matched_rules`
into `GuardResult` and both `check_input()` / `check_output()` call sites** (Revision 4,
item 1; Revision 5, item 1). `matched_rules` names the specific classifier or regex
pattern that fired (e.g. `"injection_classifier"`, `"regex:ignore_previous_instructions"`).
The middleware logs these as one structured JSON line whenever `action != ALLOW`:
```json
{"action": "BLOCK", "severity": "HIGH", "risk_score": 0.94,
 "categories": ["prompt_injection"], "matched_rules": ["injection_classifier"],
 "latency_ms": 21}
```
This is the "explainability report" a debugging session or an interviewer can be shown
directly.

### Phase 2.5 checkpoint
- [ ] A legitimate prompt containing an email is anonymized and allowed through, not blocked
- [ ] An injection attempt is still hard-blocked regardless of policy config
- [ ] Changing `policy.yaml` (e.g. `pii.HIGH: block` instead of `anonymize`) changes
      behavior with no code changes — this is the "it's configurable" proof for an interview
- [ ] The same `risk_score` produces different actions for different categories (e.g. a
      0.85 toxicity score warns, a 0.85 PII score blocks) — proves severity and action
      are genuinely decoupled, not aliases of each other
- [ ] An input containing BOTH an email and an injection payload returns `BLOCK`, not
      `ANONYMIZE` — proves the priority-order conflict resolution actually works
- [ ] A blocked request produces a structured log line with `severity`, `risk_score`,
      `categories`, `matched_rules`, and `latency_ms` populated (not empty/null)

---

## Phase 3: Red-team eval harness — this is what makes it a defensible resume claim

Same discipline as Project 1's eval harness, applied to attacks instead of Q&A quality:

- Build `redteam_cases.json` with categorized cases: direct prompt injection, indirect/
  roleplay-based jailbreaks, PII-bearing inputs, borderline-but-legitimate inputs (to check
  for false positives — a guardrail that blocks everything is useless, and testing for
  over-blocking is what separates a real safety project from a naive one), and clean control
  cases. Each case's expected result is now an **action** (`block` / `anonymize` / `warn` /
  `allow`), not a bare pass/fail — a PII case should expect `anonymize` + a specific
  `sanitized_text`, not just "flagged."
- `run_redteam.py` runs every case through the pipeline, scores the actual action against
  the expected one, and writes a results table — same format as Project 1's eval results, so
  your portfolio has a consistent, recognizable methodology across projects.
- **Report false positive rate explicitly in the README**, not just a block-rate number. A
  guardrail's real cost is legitimate requests it wrongly blocks — state this number honestly,
  the way you did with `hard-4` in Project 1, even if it's not zero.
- **Record per-check latency** (mean and p95 wall-clock time for `check_input`/
  `check_output`) while `run_redteam.py` is already running every case through the
  pipeline — near-zero extra work, and it pre-empts the "does this add noticeable latency
  in the request path" question. See Revision 2, item 4.

### Phase 3 checkpoint
- [ ] Red-team suite covers at least 4 categories (injection, jailbreak, PII, clean controls)
- [ ] Results table generated and committed, showing catch rate, false-positive rate, AND
      mean/p95 latency per check
- [ ] README states all three numbers plainly, including any known weak spots

**Phases 1-3 + 2.5 are your safe floor** — a complete, resume-ready project even if you
stop here. **Phase 5 (below) is what makes it distinctive; prioritize it over Phase 4's
polish items** if you have to choose where the remaining time goes (Revision 3, item 3).

---

## Phase 4: Polish (optional — do only after Phase 5, if time is left)

- **`examples/fastapi_app.py`: a single `POST /chat` endpoint wrapping a fake/canned LLM
  call in `check_input()`/`check_output()`** (Revision 5, item 2). One file — FastAPI
  never becomes the project, it's just the difference between someone reading a CLI
  script and someone running `curl` against a real request path and watching it get
  blocked. Skip auth, skip a real LLM call, skip anything beyond the one route.
- CI (Ruff + pytest) with badge — genuinely optional now (Revision 3, item 1). Build it
  only if you want the badge and have time after everything else; don't claim it on a CV
  until it's actually in the repo.
- Demo: wrap your actual LangGraph Report Agent's input/output with this middleware as a
  live example — a nice, honest cross-project tie-in, but keep it to a small demo script,
  not a re-integration into Project 1's real codebase
- README architecture diagram (Input → Guardrails → Policy → LLM → Guardrails → Output)

---

## Phase 5: Streaming-aware validation (new — Revision 3, item 3, the differentiator)

**Goal: show you understand that buffering a full LLM response before checking it breaks
time-to-first-token in any real streaming app — and show a working answer, not a caveat.**

- Build `StreamingGuard(window_size: int, stride: int)` in `src/guardrails/streaming.py`
  as a real reusable class, not procedural script logic (Revision 5, item 3) — this is
  GPT's repackaging of the idea, and it's a straightforward improvement: same windowing
  logic, better API. It holds its own token buffer internally; `guard.feed(token)`
  appends the token and, once the buffer reaches `window_size`, runs the toxicity/PII
  checks on the current window and returns any resulting `GuardResult`s (empty list if
  the window isn't full yet or nothing triggered).
- **Use an overlapping window, not disjoint chunks** — e.g. `window_size=40`,
  `stride=20` (Revision 4, item 3). Non-overlapping chunks guarantee some multi-token
  attacks or PII entities split across a boundary are never scored as a whole; overlap is
  the standard NLP-windowing fix and costs about the same code.
- `demo/streaming_validation.py` becomes a thin script: simulate a token-by-token
  generator (a simple generator function yielding words/tokens with small delays is
  enough — no real LLM needed), feed each token into a `StreamingGuard`, and print/log
  whatever it returns. All the actual logic lives in the reusable class, not the script.
- Measure and report the real tradeoff: compare detection accuracy and false-negative
  rate for `StreamingGuard` checking vs. full-buffer checking on the same red-team cases
  from Phase 3 — and separately, overlapping vs. non-overlapping windows, since that's the
  concrete number that proves the overlap was worth adding. Say the remaining
  false-negative rate plainly, the same way you already report false-positive rate and
  latency. This tradeoff *is* the interesting finding, not a flaw to hide.
- Keep the scope honest: this is a demonstration of the approach and its tradeoffs, not a
  production streaming implementation wired into a real LLM's token stream. Say that
  explicitly in the README so it reads as engineering judgment, not an overclaim.

### Phase 5 checkpoint
- [ ] `StreamingGuard` runs end-to-end against a simulated token stream using overlapping
      windows (stride < window size), exercised via the thin `streaming_validation.py` demo
- [ ] A results comparison exists: `StreamingGuard` vs. full-buffer detection
      accuracy/latency, AND overlapping vs. non-overlapping windows
- [ ] README states the remaining chunk-boundary false-negative tradeoff honestly, with
      a number
- [ ] `test_streaming.py` covers `StreamingGuard` directly (buffer filling, window
      eviction, detection on a window) without needing the demo script

---

## What NOT to do here

- Don't call any LLM API anywhere in the core pipeline — that's the one rule this whole
  project's design integrity depends on.
- Don't skip false-positive testing. A guardrail project that only reports catch rate is
  half a project — over-blocking is the more common real-world failure mode.
- Don't deep-integrate this into Project 1's actual production code. A small demo script
  wrapping it is enough; rewriting Project 1 to depend on this is scope creep into a
  finished, shipped project.
- Don't add an LLM-based safety judge (an LLM checking another LLM's output) — it defeats
  the entire "local, fast, doesn't depend on the thing it's policing" premise this project
  is built on.
- Don't fine-tune your own detector model — that's a separate, much larger project on its
  own, not a two-week addition to this one.
- Don't add OCR/image moderation or voice-input safety — different input modalities are a
  different problem domain and dilute the focus of what's already a complete scope.

---

## Implementation notes / known gotchas (keep in mind while building — Revision 5)

Not plan changes — Gemini's follow-up review confirmed the plan itself doesn't need
restructuring, just three physical realities worth knowing before they surprise you
mid-build:

**1. Memory footprint / OOM risk if you ever containerize this.**
Presidio with `en_core_web_lg` loaded takes roughly ~1GB RAM; add the ONNX runtime
instances for the injection classifier and toxicity classifier and total consumption
lands around 1.5-2GB. That's fine on your own machine, but it will crash immediately on
a free-tier cloud container with a hard 512MB ceiling (e.g. Render's free tier) if you
ever deploy the FastAPI demo publicly. Keep `en_core_web_lg` as the default for local
red-teaming accuracy, but add an env var (e.g. `GUARDRAILS_LITE_MODE=1`) that swaps to
`en_core_web_sm` for constrained environments, and note the recall tradeoff explicitly
in the README if you use it.

**2. Word-splitting vs. real tokenization in the streaming demo.**
`StreamingGuard` will slice a simulated token stream by whitespace/words, not by the
actual BPE subword vocabulary a real LLM uses. That's a completely reasonable
simplification for a demo — just say so in the README: *"windowing operates on
whitespace-delimited tokens for this demo harness; a production integration would bind
to the upstream model's own tokenizer."* Naming the simplification is what makes it read
as a deliberate choice instead of an oversight.

**3. PII anonymization is one-way, on purpose.**
`presidio-anonymizer` replaces sensitive values with placeholders (e.g.
`<EMAIL_ADDRESS>`) — the original value is never reconstructed or re-injected anywhere
downstream. Say this explicitly if asked: the goal of the input guardrail is to keep PII
from ever reaching a third-party LLM provider or an internal training/logging pipeline
in the first place, not to mask-and-later-unmask it. This is a design decision, not a
missing feature — don't let an interviewer read it as an oversight.

---

## Revision 6 — post-launch additions (built, tested, merged)

Everything through Phase 5 was actually built, not just planned — see README.md for
final headline numbers (100% catch rate, 40% false-positive rate, 39.6ms mean / 164.9ms
p95 latency, 45/45 tests passing). Two more items were added after Revision 5's "locked"
call, from a further external review round, and both survived the same good/useless
triage as everything before them.

**1. Pluggable detector interface (`Detector` Protocol + `GuardrailsEngine`).**
- Why kept: the three built-in detectors already shared a de facto common shape
  (confidence + matched_rules + a triggered flag) — formalizing that into a real
  `Detector` Protocol and a `register_detector()` hook was cheap (a few hours) and turns
  "three detectors" into "an extensible SDK a team could plug their own detector into,"
  a materially stronger interview claim than the same three detectors left as fixed
  internal classes.
- What shipped: `src/guardrails/detector_base.py` (the Protocol + a shared
  `DetectionSignal` type, which also absorbed the `severity_from_score` logic that used
  to live privately in `middleware.py`), `src/guardrails/builtin_detectors.py` (the three
  built-ins wrapped as real plugins, not a toy example), `src/guardrails/engine.py`
  (`GuardrailsEngine`). `check_input()`/`check_output()` in `middleware.py` are
  unaffected and remain the zero-config entry point.
- **Known gap, stated honestly: `StreamingGuard` (Phase 5) does not route through this**
  — it still calls the toxicity/PII detectors directly, so a custom detector registered
  on `GuardrailsEngine` is invisible to the streaming path. Worth closing if this project
  keeps growing; left open here rather than re-opening "final" scope for it.

**2. Versioned policy packs (`policies/strict.yaml`, `healthcare.yaml`, `enterprise.yaml`).**
- Why kept: `PolicyEngine` already took a `policy_path` constructor argument — multi-policy
  support was structurally free, it just needed named files and a selection mechanism.
  It's also the single strongest complement to the project's core "severity is model
  output, action is business policy" narrative: the same PII detection blocks under
  `healthcare` but only anonymizes under the default.
- What shipped: three genuinely different packs, not renamed copies of each other (see
  `test_policy_packs.py` for the specific action differences), `get_policy_engine(name)`,
  `GuardrailsEngine(policy_name=...)`, and a `"policy"` field on the FastAPI demo so the
  one live endpoint exercises this directly.
- **Known gap, stated honestly: `eval/run_redteam.py` only ever evaluates the default
  `policy.yaml` against `check_input()`.** The red-team suite does not run against
  `check_output()`, nor against the named policy packs. The catch-rate / false-positive-
  rate numbers in `eval/results.md` describe the default policy only.

**Discarded from the same review round:** a benchmark CLI (deprioritized — the
underlying capability already exists via `run_redteam.py`; wrapping it in `argparse`
would be polish, not new capability) and OpenTelemetry integration (real scope creep —
it needs a running collector/Grafana/Datadog to mean anything, and demonstrates generic
infra plumbing rather than anything about detection or policy, which is what this
project exists to prove).

---

**Plan status: shipped.** All phases through 5 are built, tested, and merged, plus the
two additions above. The two "known gap" notes are the honest next things to close if
this project keeps growing — not blockers, and not hidden.
