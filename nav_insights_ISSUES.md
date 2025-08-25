# nav_insights — Prioritized Backlog (with Acceptance Criteria & KPIs)

Legend: **P1 (critical)**, **P2 (important)**, **P3 (nice-to-have)**  
Labels: `[core] [dsl] [rules] [writer] [domain/search] [domain/social] [domain/clv] [infra] [docs] [eval] [security] [integration]`

---

Architecture and layering principles
- Core must be reusable: no imports from `domains/*` or `integrations/*` in `nav_insights/core/*`.
- Domain packs (e.g., `domains/paid_search`) provide IR extensions, rulesets, prompts, helpers via plugin/registry.
- Integrations adapt external systems (e.g., PaidSearchNav) into a domain pack’s IR without leaking into Core.
- “Rule of two”: only generalize Core when at least two domain packs need it; otherwise use registries/hooks.

---

## P1 — Core Foundations (general and buildable with real data)

### 1) Core IR base types (v1.0)  `[core]`
**Goal:** Define shared primitives and validation for all domains.  
**Deliverables:** `core/ir_base.py` (AccountMeta, DateRange, Evidence, AnalyzerProvenance, Finding, Totals, Aggregates, AuditFindings).  
**Acceptance Criteria:**
- Pydantic models validate sample fixtures for Search and Social (2 fixtures each).
- JSON Schema can be exported for each model.
- DateRange validator rejects `end_date < start_date`.
- Money stored as Decimal; currency code required (`{amount, currency}`), with default currency configurable.
**KPIs:**
- 100% validation pass on fixtures.
- < 5 ms validation time per IR (avg) on laptop baseline.
**Dependencies:** none.

### 2) Action & Insight schemas (v1.0)  `[core]`
**Goal:** Shared output types for downstream UIs/automation.  
**Acceptance Criteria:**
- Models serialize/deserialize without loss (`model_dump` roundtrip).
- `priority` range 1–5 enforced; `confidence` in `[0,1]`.
- Money fields include currency; round-trip preserves currency.
- Example Insight with 2 actions validates.
**KPIs:**
- 100% unit test pass.
**Dependencies:** none.

### 3) Safe expression DSL + Helper/Accessor Registry  `[dsl][core]`
**Goal:** Evaluate rule expressions safely over IR with extensibility via registries.  
**Acceptance Criteria:**
- Supports: literals, `and/or/not`, `== != < <= > >=`, `+ - * / %`, `min()/max()`, `value("a.b.c")`.
- Disallows arbitrary names/imports/attributes.
- Graceful `None` behavior: non-existent paths cause conditions to evaluate predictably (documented).
- Registry allows domain packs to register helpers (e.g., `pct`, `money`, `usd`) and value accessors without Core edits.
**KPIs:**
- 0 security findings in code review.
- 100% test pass across 30+ expression cases.
**Dependencies:** none.

### 4) Rules engine (YAML)  `[rules]`
**Goal:** Load YAML, evaluate conditions, render justifications, compute simple impacts.  
**Acceptance Criteria:**
- Given sample Search IR, starter rules emit expected actions (golden test).
- Jinja templates have helpers from registry: `pct(x)`, `money(x,currency)`, `value(path)`; USD shortcut helper lives in search domain pack.
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

### 6) Model serving infrastructure (llama.cpp and vLLM)  `[infra][writer]`
**Goal:** Reproducible local serving with CPU-optimized (llama.cpp) and GPU/throughput (vLLM) options.  
**Acceptance Criteria:**
- Script or container to launch either backend; health and readiness endpoints.
- Config-driven model/adapters loading; selection of backend via flag.
- Documented setup instructions.
**KPIs:**
- llama.cpp: p50 ≤ 2.0s @ 256 toks on 7B Q4 quant (hardware documented).
- vLLM: throughput/latency baseline documented.
**Dependencies:** Writer.

### 7) Training data pipeline (ingest historical audits)  `[eval][infra]`
**Goal:** Build reproducible pipeline from historical audits into JSONL for LoRA/QLoRA training/eval.  
**Acceptance Criteria:**
- Ingest from PaidSearchNav exports/S3; dedupe; deterministic splits; schema validation.
- Dataset builder exposes plugin hook; PaidSearchNav ingestion implemented as plugin.
**KPIs:**
- Build ≥5k train / ≥500 eval in < 10 min on laptop baseline or <5 min on CI runner.
- <2% duplicate rate; 100% JSON schema compliance.
**Dependencies:** Insight schema.

### 8) LoRA/QLoRA fine-tuning pipeline  `[writer][infra][eval]`
**Goal:** Implement reproducible fine-tuning (PEFT/QLoRA) with config-driven training jobs.  
**Acceptance Criteria:**
- Training scripts/configs (base model, lora_rank, target modules, QLoRA options) with manifest and license.
- Produces versioned adapters; evaluation step runs harness and publishes metrics.
**KPIs:**
- JSON validity improvement vs base by ≥2 pp on eval set.
- p50 inference with adapter ≤ base+10%.
**Dependencies:** Training data, Writer.

### 9) PaidSearchNav integration adapter & E2E flow  `[integration][infra]`
**Goal:** Adapter from PaidSearchNav outputs to nav_insights endpoints, preserving orchestration.  
**Acceptance Criteria:**
- Contract doc (input shape, IR generation, rules, writer call, outputs).
- Dry-run mode with file-based IRs; feature flag for staged rollout.
**KPIs:**
- E2E success rate ≥95% on sample runs; end-to-end latency <3s median (excluding data fetch).
**Dependencies:** Rules, Writer, Search domain pack.

### 10) Epic: Analyzer output → IR mapping (Search)  `[domain/search][integration][core]`
**Goal:** Define schema mapping and fixtures for every PaidSearchNav analyzer → Findings IR (search).  
**Acceptance Criteria:**
- Mapping spec per analyzer with provenance and unit conversions.
- ≥2 sample fixtures per analyzer validate against IR.
- README table tracks analyzer→IR coverage status.
**KPIs:**
- 100% analyzers mapped; 100% fixture validation pass.
**Dependencies:** Core IR base.

---

## P2 — Domain Enablement & Tooling

### 11) Search domain pack (IR + default rules)  `[domain/search][rules]`
**Goal:** Reference domain to prove the engine.  
**Acceptance Criteria:**
- `AuditFindingsSearch` extends base and validates sample IR.
- Default ruleset (≥ 12 rules) covers: match types, QS pockets, PMax overlap, geo outliers, budget pacing, tracking gaps.
- Example script prints ≥ 3 actions for sample IR.
**KPIs:**
- Rule coverage: ≥ 80% of common analyzer outputs (tracked in README).
**Dependencies:** Core, Rules.

### 12) Dataset builder integration (pluginized)  `[eval][infra]`
**Goal:** Package the builder to create JSONL datasets with plugin hooks.  
**Acceptance Criteria:**
- CLI: `python -m nav_insights.datasets.builder --input_root ...` writes `train.jsonl`/`eval.jsonl`.
- Supports `--schema_path` to embed Insight JSON schema into the system prompt.
- Synthetic label fallback when `label_insight.json` missing.
- Plugin interface for domain-specific ingestion.
**KPIs:**
- Build 1k-record dataset in < 60s on laptop baseline.
**Dependencies:** Insight schema.

### 13) Evaluation harness  `[eval]`
**Goal:** Track JSON validity, hallucinations, numeric alignment.  
**Acceptance Criteria:**
- Compute: validity rate, numeric reference accuracy vs IR, hallucination rate (mentions of entities absent from IR).
- Report to stdout/JSON; add pytest to assert thresholds.
**KPIs:**
- Validity ≥ 95% on fixtures; numeric accuracy ≥ 98%.
**Dependencies:** Writer.

### 14) Paid Social & CLV IR stubs  `[domain/social][domain/clv]`
**Goal:** Scaffold future domains.  
**Acceptance Criteria:**
- `AuditFindingsSocial` with placeholder aggregates (placement mix, frequency, CPM/CTR).
- `AuditFindingsCLV` with placeholders (cohorts, retention, CAC/LTV).
- Both import and validate minimal sample IRs.
**KPIs:**
- 100% unit test pass.
**Dependencies:** Core.

### 15) CI matrix & quality gates  `[infra]`
**Goal:** Harden CI with tests, lint/format, optional mypy, pre-commit hooks.  
**Acceptance Criteria:**
- Workflow triggers on PR/Push; caches pip; fails on test failures.
- Adds ruff check/format, pytest, and optional mypy.
**KPIs:**
- p95 CI time ≤ 4 min; pass rate ≥ 99% on main.
**Dependencies:** Tests exist.

### 16) Docs: Getting Started + RFC  `[docs]`
**Goal:** Onboard devs in < 5 minutes.  
**Acceptance Criteria:**
- README quick start (install, example, tests).
- RFC with goals, non-goals, public API, rollout, risks.
- CONTRIBUTING with commit/tag/version rules.
**KPIs:**
- New dev can run example without asking for help.
**Dependencies:** Example script.

### 17) Multi-tenant adapters (LoRA)  `[writer]` (PROMOTED from P3)
**Goal:** Hot-swap per-tenant LoRA adapters.  
**Acceptance Criteria:**
- Load adapter by `tenant_id` via config.
- LRU cache; fallback to base if adapter load fails.
**KPIs:**
- Adapter swap time ≤ 300 ms (cached).
**Dependencies:** Writer, Serving.

### 18) Model/adapter artifact storage & versioning  `[infra]`
**Goal:** Content-addressed storage with provenance and integrity checks.  
**Acceptance Criteria:**
- Manifests with checksums, dataset commit, hyperparams, license.
- Integrity verification; corruption handling.
**KPIs:**
- 100% artifact integrity; 100% cold-load success.
**Dependencies:** Serving, LoRA pipeline.

### 19) Rules authoring toolkit (linter, coverage, docs)  `[rules][dsl][docs]`
**Goal:** Improve reliability and maintainability of YAML rules.  
**Acceptance Criteria:**
- Linter for invalid references and unsupported DSL constructs.
- Coverage report: proportion of mapped IR fields referenced by at least one rule.
**KPIs:**
- 0 invalid references in CI; ≥80% target coverage for search domain.
**Dependencies:** Rules engine, Analyzer mapping.

### 20) Golden dataset & CI quality gate  `[eval][infra]`
**Goal:** Lock canonical IR inputs and expected actions/writer outputs to prevent regressions.  
**Acceptance Criteria:**
- Golden assets in repo; CI compares validity/accuracy against thresholds.
**KPIs:**
- Golden tests flakiness ≤1% across 20 consecutive CI runs.
**Dependencies:** Evaluation harness, Search domain pack.

### 21) Schema versioning & migration tools  `[core]`
**Goal:** Versioned IR with explicit migrations.  
**Acceptance Criteria:**
- `schema_version` in IR; migration helpers; docs on breaking changes.
**KPIs:**
- 100% of IR read/write paths version-aware; migrations unit-tested.
**Dependencies:** Core IR base.

### 22) Error taxonomy & structured errors  `[core][infra]`
**Goal:** Consistent error model across engine and service wrapper.  
**Acceptance Criteria:**
- Enumerated error codes (validation, rules, writer, serving); mapped to HTTP when applicable.
**KPIs:**
- 0 generic Exceptions in logs.
**Dependencies:** Core, Writer, Serving.

### 23) Core guardrails (static checks)  `[infra][core]`
**Goal:** Enforce reusable Core boundaries.  
**Acceptance Criteria:**
- Static check fails CI if `nav_insights/core/*` imports from `domains/*` or `integrations/*`.
- Dual-domain smoke tests (toy pack + search) run in CI.
**KPIs:**
- 0 violations on main; smoke tests pass on every PR.
**Dependencies:** Core, Search domain pack.

---

## P3 — Hardening & Extensions

### 24) Value accessor: dotted path with slices/filters  `[dsl]`
**Goal:** Extend `value()` to support `top_n` and simple filters.  
**Acceptance Criteria:**
- `value("index.top_broad_by_cost[:25]")` works (docs include examples).
- Safety maintained (no eval of arbitrary code).
**KPIs:**
- Zero regressions in DSL tests.
**Dependencies:** DSL.

### 25) Rules: priority & dedupe policy  `[rules]`
**Goal:** Prevent duplicate/conflicting actions; configurable priority tie-breaks.  
**Acceptance Criteria:**
- Engine supports `dedupe_key` and `max_per_type` knobs.
- Tests show collisions are resolved predictably.
**KPIs:**
- 0 duplicate user-facing actions in example outputs.
**Dependencies:** Rules engine.

### 26) Telemetry events  `[infra]`
**Goal:** Emit structured logs for rule matches and writer attempts.  
**Acceptance Criteria:**
- JSON logs for: rule_id, conditions met, action emitted, writer validity attempts, elapsed ms.
- Toggle via env var `NI_TELEMETRY=1`.
**KPIs:**
- < 2% perf overhead with telemetry on (measured).
**Dependencies:** Rules, Writer.

### 27) Telemetry → metrics & dashboard  `[infra]`
**Goal:** Export Prometheus/OpenTelemetry counters for validity, retries, latency, rule hits.  
**Acceptance Criteria:**
- Metrics emitted and parsed; minimal dashboard provided.
**KPIs:**
- Telemetry overhead <2%; metrics coverage for critical paths 100%.
**Dependencies:** Telemetry events.

### 28) Security review & fuzz tests  `[security]`
**Goal:** Harden DSL and template rendering.  
**Acceptance Criteria:**
- Fuzzed expressions do not escape sandbox.
- Templates cannot access builtins or env; helpers are whitelisted only.
**KPIs:**
- 0 critical findings from review.
**Dependencies:** DSL, Rules.

### 29) Service wrapper (optional)  `[infra]`
**Goal:** Thin FastAPI wrapper for cross-language consumers.  
**Acceptance Criteria:**
- `/v1/actions:evaluate` (IR + ruleset → actions)
- `/v1/insights:compose` (IR + actions → Insight)
- JSON schema exposed via `/v1/schemas`
**KPIs:**
- p50 latency ≤ 30 ms for actions-only endpoint (no model).
**Dependencies:** Core, Rules, Writer.

### 30) Performance experiments  `[eval]`
**Goal:** Measure cost/latency across model sizes & quantizations.  
**Acceptance Criteria:**
- Script that runs the same prompt across several gguf quantizations and logs throughput/latency/validity.
**KPIs:**
- Pick a default model that meets p50 ≤ 2s (local) and validity ≥ 95%.
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
| 6  | P1       | TBA   | 2d       | 5          |
| 7  | P1       | TBA   | 1d       | 2          |
| 8  | P1       | TBA   | 2d       | 7,5        |
| 9  | P1       | TBA   | 2d       | 5,11       |
| 10 | P1       | TBA   | 3d       | 1,11       |
| 11 | P2       | TBA   | 3d       | 1,4        |
| 12 | P2       | TBA   | 1d       | 2          |
| 13 | P2       | TBA   | 2d       | 5          |
| 14 | P2       | TBA   | 1d       | 1          |
| 15 | P2       | TBA   | 0.5d     | tests      |
| 16 | P2       | TBA   | 1d       | example    |
| 17 | P2       | TBA   | 1d       | 5,6        |
| 18 | P2       | TBA   | 1d       | 6,8        |
| 19 | P2       | TBA   | 1d       | 4,10       |
| 20 | P2       | TBA   | 1d       | 8,11       |
| 21 | P2       | TBA   | 1d       | 1          |
| 22 | P2       | TBA   | 1d       | 1,5        |
| 23 | P2       | TBA   | 1d       | 1,11       |
| 24 | P3       | TBA   | 2d       | 3          |
| 25 | P3       | TBA   | 1d       | 4          |
| 26 | P3       | TBA   | 1d       | 4,5        |
| 27 | P3       | TBA   | 1d       | 26         |
| 28 | P3       | TBA   | 1d       | 3,4        |
| 29 | P3       | TBA   | 2d       | 4,5        |
| 30 | P3       | TBA   | 1d       | 5          |

---

## Notes
- **KPIs** should be revisited after the first PaidSearchNav integration to reflect real-world baselines.
- **Golden tests**: lock sample IRs & expected actions to stabilize outputs during refactors.
- **Feature flags**: roll engine into PaidSearchNav behind a flag before broad adoption.
- **Core boundary guardrails**: CI should gate merges on no cross-layer imports and dual-domain smoke tests.
