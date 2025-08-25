Absolutely—here’s a developer-friendly `README.md` you can drop at the repo root. It explains the “why,” the architecture, how to run it, and the core APIs with short, copy-pastable examples.

---

# nav\_insights

Reusable **Insights Engine** for analytics apps (e.g., **PaidSearchNav**, **PaidSocialNav**, **CLVNav**). It turns a **typed audit IR** (Intermediate Representation) into:

* **Deterministic actions** via YAML **rules**
* Optional **human-friendly insights** via a local, low-cost **tiny LLM** (llama.cpp or vLLM), strictly validated against schema

> TL;DR: analyzers → **Findings IR** → rules → **Actions** → (optional writer) → **Insight JSON**
> Deterministic first, model-assisted narration second.

---

## Why this exists

* **Repeatable & testable**: Freeze an IR → always get the same actions and narrative.
* **Separation of concerns**: Analyzers produce *facts*, rules pick *what to do*, the model (if used) writes *how to explain*.
* **Safe & private**: Structured outputs validated with Pydantic; local models keep costs & IP in your control.
* **Reusable**: Share the engine across *Search*, *Social*, and *CLV* with domain-specific IRs and rules.

---

## Architecture (at a glance)

```
apps (PaidSearchNav / PaidSocialNav / CLVNav)
        |  domain IR + rules + prompts
        v
nav_insights (library)
  core/
    ir_base.py       # base types: IR, Finding, Evidence, Totals, Aggregates
    actions.py       # Action & Impact
    insight.py       # Insight JSON (final, structured)
    dsl.py           # value("a.b.c") + safe expression evaluator
    rules.py         # YAML rules runtime → Actions
    writer.py        # llama.cpp/vLLM client → Insight (schema-validated)
    validation.py    # helpers (minified JSON, schema export)
  domains/
    paid_search/
      ir.py          # AuditFindingsSearch (extends base IR)
      rules/*.yaml   # rules for Search
    paid_social/     # (stub)
    clv/             # (stub)
  examples/
  tests/
```

**Design principles**

* Contract-first, versioned **IR** (Pydantic)
* Deterministic rules decide **what**, LLM only helps **how**
* Structured IO (no free-form text escaping schemas)
* Domains extend **base** types; don’t over-generalize early
* Observability over rule matches and writer validity

---

## Install & quick start

```bash
# from repo root
python -m pip install -e .
python examples/compose_search_example.py
pytest
```

The example loads a small **Paid Search IR** and emits a few **Actions** using the starter ruleset.

---

## Core data models

### Findings IR (Intermediate Representation)

A versioned, Pydantic-validated object that captures one audit window:

* **account**, **date\_range**
* **totals** & **aggregates** (e.g., `match_type.broad_pct`, `quality_score.p25`)
* **findings\[]** (atomic facts with metrics + evidence)
* optional namespaces (e.g., `pmax`, `geo`)
* **provenance** (queries/checksums/analyzer versions)

Search extends the base IR in `domains/paid_search/ir.py`.

### Actions

Deterministic recommendations from the rules engine:

```python
Action(
  id="BROAD_TOO_HIGH_LOW_QS_ACT_1",
  type="tighten_match_types",
  target="top_broad_by_cost",
  params={"limit":25,"new_match":"phrase"},
  justification="Broad share is 52% with QS p25 at 4.3. …",
  expected_impact=ActionImpact(spend_savings_usd=4200, risk="low"),
  priority=1, confidence=0.9, source_rule_id="BROAD_TOO_HIGH_LOW_QS"
)
```

### Insight (optional writer output)

A strictly-typed, UI-ready narrative with sections, bullets, and embedded **Actions**.

---

## Rules DSL (YAML)

Write conditions over the IR using a safe DSL and render justifications via Jinja:

```yaml
- id: BROAD_TOO_HIGH_LOW_QS
  if_all:
    - expr: 'value("aggregates.match_type.broad_pct") >= 0.40'
    - expr: 'value("aggregates.quality_score.p25") < 5'
  action:
    type: "tighten_match_types"
    target: "top_broad_by_cost"
    params: { limit: 25, new_match: "phrase" }
  justification_template: >
    Broad share is {{ pct(value("aggregates.match_type.broad_pct")) }}
    with QS p25 at {{ value("aggregates.quality_score.p25") }}.
  expected_impact:
    spend_savings_usd: 'value("metrics.wasted_spend_top_broad")'
    risk: "low"
  priority: 1
```

Helpers available in templates:

* `value("a.b.c")` — read any dotted path from IR
* `pct(x)` — 0.52 → `52%`
* `usd(x)` — 1300 → `$1,300`

---

## Programmatic use

### Evaluate actions from an IR

```python
import json, pathlib
from nav_insights.core.rules import evaluate_rules

BASE = pathlib.Path(__file__).parent
ir = json.loads((BASE / "examples" / "sample_ir_search.json").read_text())
rules_path = str(BASE / "nav_insights" / "domains" / "paid_search" / "rules" / "default.yaml")

actions = evaluate_rules(ir, rules_path)
for a in actions:
    print(a.model_dump())
```

### Compose an Insight via a tiny local model (optional)

You can run **llama.cpp** or **vLLM** with an OpenAI-compatible endpoint.

```python
from nav_insights.core.writer import compose_insight_json
from nav_insights.core.insight import Insight

insight = compose_insight_json(
    ir=ir,
    actions=actions,
    schema_model=Insight,
    base_url="http://localhost:8000/v1",
    model="local"
)
print(insight.model_dump_json(indent=2))
```

The writer first tries a JSON-Schema/Grammar mode (if the server supports it), and otherwise retries with strict “JSON-only” prompting. All outputs must validate against the **Insight** schema.

---

## Directory layout

```
nav_insights/
  core/
    actions.py        # Action & ActionImpact
    dsl.py            # safe expression evaluator + value()
    insight.py        # Insight schema
    ir_base.py        # base IR
    rules.py          # YAML rules engine
    validation.py     # helpers
    writer.py         # llama.cpp/vLLM wrapper
  domains/
    paid_search/
      ir.py
      rules/
        default.yaml
    paid_social/      # stub
    clv/              # stub
examples/
  compose_search_example.py
  sample_ir_search.json
tests/
.github/workflows/ci.yml
RFC.md
ISSUES.md
```

---

## Configuration & conventions

* **Units**: Rates in `[0,1]`; money as `Decimal USD` (or consistent cents as ints).
* **Versioning**: IR has `schema_version`. Bump on breaking changes; keep migrations nearby.
* **Safety**:

  * DSL whitelists AST nodes; no imports/globals/attributes beyond `value()`, `min`, `max`.
  * Jinja context is sandboxed with only helper functions; no builtins exposed.
* **Performance**: Rules evaluation is fast; writer depends on your model/quantization.

---

## Contributing

1. Read `RFC.md` (goals, non-goals, API, rollout).
2. Open an issue from `ISSUES.md` (prioritized backlog with acceptance criteria & KPIs).
3. Add tests for new behavior (`pytest` must pass).
4. For IR or Insight changes, bump schema/package versions and update fixtures.

---

## Analyzer → IR Coverage Status

This table tracks the mapping status of PaidSearchNav analyzers to the Core IR:

| Analyzer | Status | IR Mapping | Fixtures | Tests | Issue |
|----------|--------|------------|----------|-------|--------|
| **negative_conflicts** | ✅ Complete | [spec](docs/mappings/paid_search/negative_conflicts_to_ir.md) | 2 fixtures | 11 tests | [#39](https://github.com/datablogin/nav-insights/issues/39) |
| **search_terms** | 📝 Draft | [spec](docs/mappings/paid_search/search_terms_to_ir.md) | - | - | - |
| **keyword_analyzer** | 📝 Draft | [spec](docs/mappings/paid_search/keyword_analyzer_to_ir.md) | - | - | - |
| **competitor_insights** | 📝 Draft | [spec](docs/mappings/paid_search/competitor_insights_to_ir.md) | - | - | - |
| geo_performance | 🔲 Pending | - | - | - | - |
| quality_score | 🔲 Pending | - | - | - | - |
| bid_efficiency | 🔲 Pending | - | - | - | - |
| match_type_analysis | 🔲 Pending | - | - | - | - |
| search_impression_share | 🔲 Pending | - | - | - | - |
| *...additional analyzers...* | 🔲 Pending | - | - | - | - |

**Legend:**
- ✅ Complete: Mapping spec, fixtures, and tests implemented
- 📝 Draft: Mapping spec exists, needs fixtures/tests  
- 🔲 Pending: Not yet started

**Coverage Stats:**
- Total analyzers: 20+ (from PaidSearchNav)
- Mapped: 1 (5%)
- Target: 16+ (80% coverage for P2 milestone)

---

## Roadmap (highlights)

* **P1**: Core IR/Actions/Insight, DSL, rules engine, writer with schema enforcement
* **P2**: PaidSearch rules (≥12), dataset builder integration, evaluation harness, analyzer→IR coverage ≥80%
* **P3**: Dedupe/priority policy, telemetry, optional FastAPI service wrapper

See `ISSUES.md` for the full list.

---

## FAQ

**Q: Do I need the model to use nav\_insights?**
No. Rules → **Actions** is fully deterministic. The model is optional for generating narrative **Insight** JSON.

**Q: Which models are supported?**
Anything behind an **OpenAI-compatible** chat endpoint (e.g., llama.cpp servers, vLLM). Start with a 7B Q4 quant for speed.

**Q: Can I bring my own schema?**
Yes—`Insight` is default. You can validate against your own Pydantic model; the writer enforces whatever schema you pass.

**Q: How do I extend for Social or CLV?**
Create a domain IR that extends `core.ir_base.AuditFindings`, add rules under `domains/<domain>/rules`, and point the engine at that ruleset.

---

## License

MIT

---
