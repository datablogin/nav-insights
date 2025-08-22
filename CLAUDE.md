# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Problem Context

**IMPORTANT**: Read `PROBLEM_DEFINITION.md` first to understand the complete problem scope, architecture, and requirements. This engine processes outputs from 20 PaidSearchNav analyzers and requires LoRA-based fine-tuning capabilities.

## Development Commands

**Install and setup:**
```bash
python -m pip install -e .
```

**Run tests:**
```bash
pytest
```

**Run example:**
```bash
python examples/compose_search_example.py
```

## Architecture Overview

This is a reusable insights engine that transforms typed audit data into deterministic actions and optional AI-generated insights. The core workflow:

```
IR (Intermediate Representation) → Rules Engine → Actions → Writer (optional) → Insights
```

### Core Components

- **`nav_insights.core.findings_ir`**: Base IR schema with Finding, Evidence, Totals, Aggregates
- **`nav_insights.core.rules`**: YAML rules engine that evaluates conditions and generates Actions
- **`nav_insights.core.dsl`**: Safe expression evaluator for rules (whitelisted AST nodes only)
- **`nav_insights.core.actions`**: Action and ActionImpact types
- **`nav_insights.core.writer`**: Optional LLM client for generating narrative insights
- **`nav_insights.core.insight`**: Final structured output schema

### Domain Extensions

Each domain extends the base IR:
- **`nav_insights.domains.paid_search.ir`**: Search-specific IR extensions
- **`nav_insights.domains.paid_search.rules/default.yaml`**: Search-specific YAML rules

### Rules DSL

Rules use a safe expression evaluator with these functions:
- `value("path.to.field")` - Access IR data via dot notation
- `pct(x)` - Format as percentage (0.52 → "52%")
- `usd(x)` - Format as currency (1300 → "$1,300")

Example rule structure:
```yaml
- id: RULE_ID
  if_all:
    - expr: 'value("aggregates.match_type.broad_pct") >= 0.40'
  action:
    type: "action_type"
    target: "target_entity"
    params: {key: value}
  justification_template: "Template with {{ value('field') }}"
  expected_impact:
    spend_savings_usd: 'value("metrics.field")'
  priority: 1
```

### Data Types and Conventions

- **Rates**: Store as decimals in [0,1] range (use Rate01/Pct01 types)
- **Money**: Store as Decimal USD (use USD type)
- **Schema versioning**: IR includes `schema_version` field
- **Safety**: DSL whitelists AST nodes, Jinja context is sandboxed

### Testing Patterns

Tests use JSON fixtures and validate rule evaluation:
```python
ir = json.loads((base / "examples" / "sample_ir_search.json").read_text())
rules_path = str(base / "nav_insights" / "domains" / "paid_search" / "rules" / "default.yaml")
actions = evaluate_rules(ir, rules_path)
```