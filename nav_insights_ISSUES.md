# nav_insights — Prioritized Backlog (with Acceptance Criteria & KPIs)

Legend: **P1 (critical)**, **P2 (important)**, **P3 (nice-to-have)**  
Labels: `[core] [dsl] [rules] [writer] [domain/search] [domain/social] [domain/clv] [infra] [docs] [eval] [security]`

---

## P1 — Core Foundations

### 1) Core IR base types (v1.0)  `[core]`
**Goal:** Define shared primitives and validation for all domains.  
**Deliverables:** `core/ir_base.py` (AccountMeta, DateRange, Evidence, AnalyzerProvenance, Finding, Totals, Aggregates, AuditFindings).  
**Acceptance Criteria:**
- Pydantic models validate sample fixtures for Search and Social (2 fixtures each).
- JSON Schema can be exported for each model.
- DateRange validator rejects `end_date < start_date`.
- Money stored as Decimal (USD) and rates in `[0,1]`.
**KPIs:**
- 100% validation pass on fixtures.
- < 5 ms validation time per IR (avg) on laptop baseline.
**Dependencies:** none.

### 2) Action & Insight schemas (v1.0)  `[core]`
**Goal:** Shared output types for downstream UIs/automation.  
**Acceptance Criteria:**
- Models serialize/deserialize without loss (`model_dump` roundtrip).
- `priority` range 1–5 enforced; `confidence` in `[0,1]`.
- Example Insight with 2 actions validates.
**KPIs:**
- 100% unit test pass.
**Dependencies:** none.

### 3) Safe expression DSL  `[dsl]`
**Goal:** Evaluate rule expressions safely over IR.  
**Acceptance Criteria:**
- Supports: literals, `and/or/not`, `== != < <= > >=`, `+ - * / %`, `min()/max()`, `value("a.b.c")`.
- Disallows arbitrary names/imports/attributes.
- Graceful `None` behavior: non-existent paths cause conditions to evaluate predictably (documented).
**KPIs:**
- 0 security findings in code review.
- 100% test pass across 30+ expression cases.
**Dependencies:** none.

### 4) Rules engine (YAML)  `[rules]`
**Goal:** Load YAML, evaluate conditions, render justifications, compute simple impacts.  
**Acceptance Criteria:**
- Given sample Search IR, starter rules emit expected actions (golden test).
- Jinja templates have helpers: `pct(x)`, `usd(x)`, `value(path)`.
- `expected_impact` supports scalar expressions and dicts.
- Deterministic order of actions per ruleset.
**KPIs:**
- Golden tests stable across 10 consecutive runs.
- < 15 ms median evaluation time for 100 rules & single IR on laptop baseline.
**Dependencies:** DSL.

### 5) Writer (tiny LLM) with schema enforcement  `[writer]`
**Goal:** Generate Insight JSON via llama.cpp/vLLM with pydantic validation and retry.  
**Acceptance Criteria:**
- Supports OpenAI-compatible Chat endpoint.
- Tries JSON-Schema/Grammar mode; falls back to strict JSON-only prompt+retry (2 attempts).
- Returns validated `Insight` or raises structured error.
**KPIs:**
- ≥ 95% validity on internal fixtures without manual retry.
- p50 latency ≤ 2.0s on local 7B Q4 quant @ 256 toks (document your hardware).
**Dependencies:** Insight schema.

---

## P2 — Domain Enablement & Tooling

### 6) Paid Search IR + default rules  `[domain/search][rules]`
**Goal:** Reference domain to prove the engine.  
**Acceptance Criteria:**
- `AuditFindingsSearch` extends base and validates sample IR.
- Default ruleset (≥ 12 rules) covers: match types, QS pockets, PMax overlap, geo outliers, budget pacing, tracking gaps.
- Example script prints ≥ 3 actions for sample IR.
**KPIs:**
- Rule coverage: ≥ 80% of common analyzer outputs (tracked in README).
**Dependencies:** Core, Rules.

### 7) Dataset builder integration  `[eval][infra]`
**Goal:** Package the existing builder to create JSONL training data.  
**Acceptance Criteria:**
- CLI: `python -m nav_insights.datasets.builder --input_root ...` writes `train.jsonl`/`eval.jsonl`.
- Supports `--schema_path` to embed Insight JSON schema into the system prompt.
- Synthetic label fallback when `label_insight.json` missing.
**KPIs:**
- Build 1k-record dataset in < 60s on laptop baseline.
**Dependencies:** Insight schema.

### 8) Evaluation harness  `[eval]`
**Goal:** Track JSON validity, hallucinations, numeric alignment.  
**Acceptance Criteria:**
- Compute: validity rate, numeric reference accuracy vs IR, hallucination rate (mentions of entities absent from IR).
- Report to stdout/JSON; add pytest to assert thresholds.
**KPIs:**
- Validity ≥ 95% on fixtures; numeric accuracy ≥ 98%.
**Dependencies:** Writer.

### 9) Paid Social & CLV IR stubs  `[domain/social][domain/clv]`
**Goal:** Scaffold future domains.  
**Acceptance Criteria:**
- `AuditFindingsSocial` with placeholder aggregates (placement mix, frequency, CPM/CTR).
- `AuditFindingsCLV` with placeholders (cohorts, retention, CAC/LTV).
- Both import and validate minimal sample IRs.
**KPIs:**
- 100% unit test pass.
**Dependencies:** Core.

### 10) CI pipeline  `[infra]`
**Goal:** GitHub Actions running pytest with Python 3.11.  
**Acceptance Criteria:**
- Workflow triggers on PR/Push.
- Caches pip; fails on test failures.
**KPIs:**
- p95 CI time ≤ 4 min.
**Dependencies:** Tests exist.

### 11) Docs: Getting Started + RFC  `[docs]`
**Goal:** Onboard devs in < 5 minutes.  
**Acceptance Criteria:**
- README quick start (install, example, tests).
- RFC with goals, non-goals, public API, rollout, risks.
- CONTRIBUTING with commit/tag/version rules.
**KPIs:**
- New dev can run example without asking for help.
**Dependencies:** Example script.

---

## P3 — Hardening & Extensions

### 12) Value accessor: dotted path with slices/filters  `[dsl]`
**Goal:** Extend `value()` to support `top_n` and simple filters.  
**Acceptance Criteria:**
- `value("index.top_broad_by_cost[:25]")` works (docs include examples).
- Safety maintained (no eval of arbitrary code).
**KPIs:**
- Zero regressions in DSL tests.
**Dependencies:** DSL.

### 13) Rules: priority & dedupe policy  `[rules]`
**Goal:** Prevent duplicate/conflicting actions; configurable priority tie-breaks.  
**Acceptance Criteria:**
- Engine supports `dedupe_key` and `max_per_type` knobs.
- Tests show collisions are resolved predictably.
**KPIs:**
- 0 duplicate user-facing actions in example outputs.
**Dependencies:** Rules engine.

### 14) Telemetry events  `[infra]`
**Goal:** Emit structured logs for rule matches and writer attempts.  
**Acceptance Criteria:**
- JSON logs for: rule_id, conditions met, action emitted, writer validity attempts, elapsed ms.
- Toggle via env var `NI_TELEMETRY=1`.
**KPIs:**
- < 2% perf overhead with telemetry on (measured).
**Dependencies:** Rules, Writer.

### 15) Security review & fuzz tests  `[security]`
**Goal:** Harden DSL and template rendering.  
**Acceptance Criteria:**
- Fuzzed expressions do not escape sandbox.
- Templates cannot access builtins or env; helpers are whitelisted only.
**KPIs:**
- 0 critical findings from review.
**Dependencies:** DSL, Rules.

### 16) Service wrapper (optional)  `[infra]`
**Goal:** Thin FastAPI wrapper for cross-language consumers.  
**Acceptance Criteria:**
- `/v1/actions:evaluate` (IR + ruleset → actions)
- `/v1/insights:compose` (IR + actions → Insight)
- JSON schema exposed via `/v1/schemas`
**KPIs:**
- p50 latency ≤ 30 ms for actions-only endpoint (no model).
**Dependencies:** Core, Rules, Writer.

### 17) Performance experiments  `[eval]`
**Goal:** Measure cost/latency across model sizes & quantizations.  
**Acceptance Criteria:**
- Script that runs the same prompt across several gguf quantizations and logs throughput/latency/validity.
**KPIs:**
- Pick a default model that meets p50 ≤ 2s (local) and validity ≥ 95%.
**Dependencies:** Writer.

### 18) Multi-tenant adapters (LoRA)  `[writer]`
**Goal:** Hot-swap per-tenant LoRA adapters.  
**Acceptance Criteria:**
- Load adapter by `tenant_id` via config.
- Fallback to base if adapter load fails.
**KPIs:**
- Adapter swap time ≤ 300 ms (cached).
**Dependencies:** Writer.

---

## Tracking Table (Initial Owners & Estimates)

| ID | Priority | Owner | Estimate | Depends On |
|----|----------|-------|----------|------------|
| 1  | P1       | TBA   | 2d       | -          |
| 2  | P1       | TBA   | 1d       | 1          |
| 3  | P1       | TBA   | 2d       | 1          |
| 4  | P1       | TBA   | 2d       | 3          |
| 5  | P1       | TBA   | 2d       | 2,4        |
| 6  | P2       | TBA   | 3d       | 1,4        |
| 7  | P2       | TBA   | 1d       | 2          |
| 8  | P2       | TBA   | 2d       | 5          |
| 9  | P2       | TBA   | 1d       | 1          |
| 10 | P2       | TBA   | 0.5d     | tests      |
| 11 | P2       | TBA   | 1d       | example    |
| 12 | P3       | TBA   | 2d       | 3          |
| 13 | P3       | TBA   | 1d       | 4          |
| 14 | P3       | TBA   | 1d       | 4,5        |
| 15 | P3       | TBA   | 1d       | 3,4        |
| 16 | P3       | TBA   | 2d       | 4,5        |
| 17 | P3       | TBA   | 1d       | 5          |
| 18 | P3       | TBA   | 1d       | 5          |

---

## Notes
- **KPIs** should be revisited after the first PaidSearchNav integration to reflect real-world baselines.
- **Golden tests**: lock sample IRs & expected actions to stabilize outputs during refactors.
- **Feature flags**: roll engine into PaidSearchNav behind a flag before broad adoption.
