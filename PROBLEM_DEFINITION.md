# Problem Definition: nav_insights Engine

## Executive Summary

We are building a reusable insights engine that transforms outputs from 20 PaidSearchNav analyzers into deterministic actions and AI-generated narrative insights. The system combines rule-based decision making (80%) with fine-tuned local LLM narrative generation (20%) to create a hybrid reasoning layer.

## Current State: PaidSearchNav System

### 20 Production Analyzers
Located at `/Users/robertwelborn/PycharmProjects/PaidSearchNav/paidsearchnav/analyzers/`:

1. **ad_group_performance.py** - Ad group performance analysis
2. **advanced_bid_adjustment.py** - Bid adjustment recommendations  
3. **bulk_negative_manager.py** - Bulk negative keyword management
4. **campaign_overlap.py** - Campaign overlap detection
5. **competitor_insights.py** - Competitor analysis
6. **dayparting.py** - Day/time performance analysis
7. **demographics.py** - Demographic performance analysis
8. **device_performance.py** - Device performance analysis
9. **geo_performance.py** - Geographic performance analysis
10. **keyword_analyzer.py** - Keyword analysis
11. **keyword_match.py** - Match type analysis
12. **landing_page.py** - Landing page performance
13. **local_reach_store_performance.py** - Local reach and store performance
14. **negative_conflicts.py** - Negative keyword conflicts
15. **placement_audit.py** - Placement performance audit
16. **pmax.py** - Performance Max analysis
17. **search_term_analyzer.py** - Search term analysis
18. **search_terms.py** - Search terms performance
19. **search_negatives.py** - Shared negative lists
20. **store_performance.py** - Store-level performance
21. **video_creative.py** - Video creative performance

### Existing Infrastructure
- REST API with workflow orchestration
- S3/customer management  
- Report generation and recommendations export
- Scheduler with 20+ analyzer execution
- WebSocket/SSE progress updates
- Google Ads Editor file exports

## Target Solution: nav_insights Engine

### Core Architecture
```
20 Analyzers → Findings IR → Rules Engine → Actions → Writer (LoRA-tuned LLM) → Insight JSON
```

### Key Components

#### 1. Findings IR (Intermediate Representation)
- **Pydantic schemas** normalizing all 20 analyzer outputs
- **Versioned contract** (`schema_version: "1.0.0"`)
- **Base types**: Finding, Evidence, Totals, Aggregates, EntityRef
- **Domain-specific extensions** for paid search

#### 2. Rules Engine  
- **YAML decision tables** with safe expression DSL
- **Deterministic actions** from rule conditions
- **Jinja templating** for justifications with helpers (`pct()`, `usd()`, `value()`)
- **~100 rules** covering 80%+ of common scenarios

#### 3. Writer Service (MANDATORY)
- **Fine-tuned local LLM** (Mistral-7B or Llama-3.1-8B)
- **LoRA/QLoRA adapters** for tenant customization
- **Schema-enforced outputs** (strict Pydantic validation)
- **llama.cpp or vLLM** serving infrastructure

#### 4. Multi-tenant LoRA System
- **Hot-swappable adapters** by tenant_id
- **Base model fallback** if adapter fails
- **Adapter swap time** ≤ 300ms (cached)

### Technical Requirements

#### Model Strategy
- **Base models**: Mistral-7B (Apache-2.0) or Llama-3.1-8B (commercial-friendly)
- **Quantization**: Q4_K_M for CPU deployment
- **Serving**: llama.cpp (CPU-optimized) or vLLM (GPU/throughput)
- **Fine-tuning**: LoRA adapters trained on historical audit data

#### Performance Targets
- **Rule evaluation**: <15ms for 100 rules on single IR
- **LLM inference**: p50 ≤ 2.0s for 256 tokens on local 7B Q4 quant
- **JSON validity**: ≥95% without manual retry
- **Adapter switching**: ≤300ms cached

#### Safety & Compliance
- **DSL security**: Whitelisted AST nodes, no arbitrary code execution
- **Template sandboxing**: Jinja context restricted to helper functions
- **Schema enforcement**: All LLM outputs validated against Pydantic
- **Commercial licensing**: Apache-2.0 or equivalent permissive licenses

### Domain Focus
- **Primary**: Paid Search (immediate implementation)
- **Future**: Paid Social, CLV (extensible architecture)
- **Scope**: Rules and IR designed for search domain first

## Critical Success Factors

### 1. LoRA Implementation Challenge
The most complex technical requirement is implementing **LoRA/QLoRA fine-tuning** with:
- Local serving infrastructure (llama.cpp/vLLM)
- Multi-tenant adapter management
- Quality narrative generation for search domain

### 2. Quality Requirements  
- **Deterministic backbone**: Rules handle majority of decisions
- **LLM enhancement**: Narrative quality and edge case handling
- **Validation**: All outputs must pass schema validation

### 3. Integration Points
- Slots into existing PaidSearchNav infrastructure
- Maintains current REST API contracts
- Preserves workflow orchestration patterns
- Keeps Google Ads Editor export compatibility

## Non-Goals
- **No commercial APIs**: OpenAI, Claude, etc. (cost/IP concerns)
- **No free-form text**: All outputs schema-validated
- **No analyzer rewrites**: Engine consumes existing analyzer outputs
- **No immediate multi-domain**: Focus on search first

## Success Metrics
- **Rule coverage**: ≥80% of analyzer outputs handled deterministically
- **Narrative quality**: Human evaluation of LLM-generated insights
- **Performance**: Sub-second rule evaluation, <3s end-to-end
- **Reliability**: ≥95% successful insight generation without intervention

## Repository Context
- **nav_insights**: This engine (reusable library)
- **PaidSearchNav**: Production system with 20 analyzers
- **Integration**: nav_insights consumed by PaidSearchNav via API

This problem definition serves as the single source of truth for all development decisions and architectural choices.