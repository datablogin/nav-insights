
# What the Findings IR is

A **versioned, pydantic-validated object** that consolidates all analyzer outputs for one audit window into:

* **Account + window metadata**
* **Totals & aggregates** (canonical metrics used in rules)
* A list of **atomic findings** (normalized facts with metrics & evidence)
* **Provenance** (where numbers came from, code/git versions, checksums)
* Optional **indexes** (to quickly address entities like campaigns/keywords)

It is the *only* input your reasoning layer needs. Rules read it deterministically; the tiny LLM (if used) only writes the narrative **about** it—never inventing numbers.

---

# Why you need it

1. **Determinism & reproducibility**
   The IR is a frozen record of “what we saw.” You can re-run rules later and get the same outputs.

2. **Testability**
   You can unit-test rules and writers against **saved IR fixtures** (no API calls required).

3. **Separation of concerns**
   Analyzers evolve independently from rules and narrative. As long as they populate the IR, the rest of the system is stable.

4. **Multi-tenant governance**
   The IR captures provenance and schema versioning; you can audit how a recommendation was produced.

5. **Performance & caching**
   Persist IRs (e.g., in S3/DB) and skip recomputation for re-runs, diffs, and regression tests.

---

# Design principles

* **Typed + versioned**: include `schema_version`. Bump it on breaking changes.
* **Atomic facts + rollups**: mix *atomic* `Finding` objects with *aggregates/totals* for rules that don’t need ID-level detail.
* **Metrics not prose**: IR is numbers + refs; prose is created later.
* **Stable naming**: `metrics` are machine-friendly; use consistent units (e.g., rates in `[0,1]`, money in USD cents or Decimal).
* **Provenance-first**: every metric should be traceable to a query/extract and (ideally) a checksum.
* **Immutability**: IRs are read-only after generation.

---

# Detailed Pydantic schema (drop-in)

```python
# findings_ir.py  (Pydantic v2; works with v1 via model_json_schema fallback)
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, condecimal, confloat, model_validator

# ---------- Core scalar types ----------
USD = condecimal(ge=0, max_digits=18, decimal_places=4)        # store as Decimal; convert to cents downstream if preferred
Rate01 = condecimal(ge=0, le=1, max_digits=6, decimal_places=5)  # probabilities/ratios in [0,1]
Pct01 = Rate01  # alias for clarity

# ---------- Dimensions / entity references ----------
class EntityType(str, Enum):
    account = "account"
    campaign = "campaign"
    ad_group = "ad_group"
    keyword = "keyword"
    search_term = "search_term"
    geo = "geo"
    device = "device"
    audience = "audience"
    placement = "placement"
    other = "other"

class EntityRef(BaseModel):
    type: EntityType
    id: str = Field(..., description="Provider/native id or stable synthetic key")
    name: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)  # e.g., match_type, network, iso_region

# ---------- Evidence & provenance ----------
class Evidence(BaseModel):
    source: str = Field(..., description='e.g., "google_ads.query" or "ga4.export"')
    query: Optional[str] = Field(None, description="SQL/GAQL/API filter; optional if sensitive")
    rows: Optional[int] = Field(None, description="Row count contributing to this metric/finding")
    sample: List[Dict[str, Any]] = Field(default_factory=list, description="Small sample of rows for review")
    checksum: Optional[str] = Field(None, description="Hash of sorted rows or file chunk")
    entities: List[EntityRef] = Field(default_factory=list)

class AnalyzerProvenance(BaseModel):
    name: str                              # e.g., "match_type_share", "pmax_overlap"
    version: str                           # your analyzer module/version
    git_sha: Optional[str] = None          # code revision
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

# ---------- Finding ----------
class FindingCategory(str, Enum):
    structure = "structure"
    keywords = "keywords"
    quality = "quality"
    pmax = "pmax"
    geo = "geo"
    budget = "budget"
    tracking = "tracking"
    creative = "creative"
    conflicts = "conflicts"
    other = "other"

class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class Finding(BaseModel):
    id: str                                 # stable key within the audit (e.g., "KW_BROAD_SHARE_TOO_HIGH")
    category: FindingCategory
    summary: str                            # short machine-readable blurb
    description: Optional[str] = None       # optional richer description (still not the end-user prose)
    severity: Severity = Severity.medium
    confidence: confloat(ge=0.0, le=1.0) = 0.9

    # Entity(ies) this finding refers to (campaigns, keywords, regions, etc.)
    entities: List[EntityRef] = Field(default_factory=list)

    # Dimensions: tags/labels to filter findings (e.g., brand/non-brand, network=Search)
    dims: Dict[str, Any] = Field(default_factory=dict)

    # Metrics: the actual numbers rules/readers will use.
    # Keep units consistent: rates in [0,1], money in USD (Decimal), counts ints/floats.
    metrics: Dict[str, Decimal] = Field(default_factory=dict)

    # Evidence & where this came from
    evidence: List[Evidence] = Field(default_factory=list)
    provenance: Optional[AnalyzerProvenance] = None

# ---------- Totals & aggregates ----------
class AccountMeta(BaseModel):
    account_id: str
    account_name: Optional[str] = None

class DateRange(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self

class Totals(BaseModel):
    spend_usd: USD = Decimal("0")
    clicks: int = 0
    impressions: int = 0
    conversions: Decimal = Decimal("0")
    revenue_usd: USD = Decimal("0")
    # add more canonical totals you rely on (cpa_usd, roas, ctr, etc.) as *derived* at merge-time if you prefer

class Aggregates(BaseModel):
    match_type: Dict[str, Pct01] = Field(default_factory=dict)     # {"broad_pct": 0.52, "phrase_pct": 0.28, ...}
    quality_score: Dict[str, Decimal] = Field(default_factory=dict) # {"p25": 4.3, "median": 6.1}
    devices: Dict[str, Pct01] = Field(default_factory=dict)         # {"mobile": 0.63, "desktop": 0.31, ...}
    # any other grouped rollups you reference in rules (geo, pmax overlap, brand share, etc.)

# ---------- The IR root ----------
class AuditFindings(BaseModel):
    schema_version: str = "1.0.0"
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    account: AccountMeta
    date_range: DateRange

    totals: Totals
    aggregates: Aggregates = Field(default_factory=Aggregates)

    # analyzer-specific namespaces for convenience (optional, keep light)
    pmax: Dict[str, Decimal] = Field(default_factory=dict)      # e.g., {"overlap_share":0.23, "delta_roas_vs_search":-0.18, ...}
    conflicts: Dict[str, Decimal] = Field(default_factory=dict) # e.g., {"negatives_blocking_converters_count": 7}
    geo: Dict[str, Decimal] = Field(default_factory=dict)       # e.g., {"low_cr_outliers_count": 4, "savings_estimate": 900}

    # the atomic facts
    findings: List[Finding]

    # map-like indexes for fast lookups (optional)
    index: Dict[str, Any] = Field(default_factory=dict)

    # Global provenance
    data_sources: List[Evidence] = Field(default_factory=list)
    analyzers: List[AnalyzerProvenance] = Field(default_factory=list)

    # Helpful derived flags
    completeness: Dict[str, bool] = Field(default_factory=dict)  # e.g., {"tracking_ok": True, "has_pmax_data": True}

    @model_validator(mode="after")
    def _sanity(self):
        # Example sanity checks (tune to your needs)
        if self.totals.spend_usd < 0:
            raise ValueError("Totals.spend_usd cannot be negative")
        return self
```

### Why these fields exist

* **`totals`/`aggregates`**: speed up rule-writing (“match\_type.broad\_pct >= 0.40”).
* **`findings[]`**: encode *atomic* facts with **metrics + entities + evidence** so rules can filter precisely (e.g., “keywords with broad match + QS p25 < 5”).
* **`provenance/evidence`**: enable trust & audits. If someone asks “where did 0.52 come from?”, you can show the query/checksum.
* **`index`**: optional precomputed maps (e.g., `index["keyword_by_id"][kw_id]`) to avoid re-joining during rules.
* **`schema_version`**: lets you migrate old IRs without breaking consumers.

---

# How to build it (practical steps)

1. **Define the contract first**
   Start with the code above. Save as `findings_ir.py`. Treat it as a public API between analyzers and reasoning.

2. **Make adapters per analyzer**
   Each analyzer returns a list of `Finding` objects + any namespace dicts it owns (e.g., `pmax`, `conflicts`) and contributes to `aggregates`. Keep analyzers **pure** (input → output) and side-effect free.

3. **Merge step (builder)**

   * **Initialize** an empty `AuditFindings` with account/date window and zero totals.
   * **Fold** in analyzer outputs:

     * Extend `findings`.
     * Update `aggregates` keys (e.g., `match_type.broad_pct`, `quality_score.p25`).
     * Update namespace dicts (`pmax`, `conflicts`, `geo`) for convenience.
     * Accumulate `totals` and compute derived metrics (CPA/ROAS) if needed.
   * **Attach provenance** (analyzer name, version, git sha).
   * **Validate** with pydantic. If it fails, reject the build and log.

4. **Naming/units conventions**

   * Rates in `[0,1]` (not 0–100).
   * Money as `Decimal` USD (or cents as `int` if you prefer).
   * Keep metric keys short, consistent, and machine-friendly: `broad_pct`, `qs_p25`, `overlap_share`, `wasted_spend_top_broad`.

5. **Evidence**

   * For heavy tables, just store a **checksum** and the **row count**, plus a **tiny sample** (≤ 5 rows).
   * For sensitive queries, omit the query text but keep a symbolic name and checksum.

6. **Indexes (optional)**

   * If your rules frequently need fast lookups (e.g., “top N broad keywords by spend”), precompute and place in `index` (e.g., `{"top_broad_by_cost":[<keyword ids>]}`).

7. **Persistence**

   * Serialize to JSON (UTF-8, canonical sort) and store with a content hash:
     `s3://…/ir/{account_id}/{start-end}/{schema_version}/{sha256}.json`
   * This becomes your replay artifact for rules/LLM/regression tests.

---

# How rules & the tiny LLM use it

* **Rules** read the IR:

  ```yaml
  - id: BROAD_TOO_HIGH_LOW_QS
    if_all:
      - expr: 'value("aggregates.match_type.broad_pct") >= 0.40'
      - expr: 'value("aggregates.quality_score.p25") < 5'
    # …
  ```

  Having those aggregates in the IR makes conditions short and reliable.

* **Tiny LLM** only receives the IR (or a distilled subset) and must return **strict `Insight` JSON**. The IR ensures the writer references **real metrics**, not guesses.

---

# Minimal example (shape)

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2025-08-19T18:05:00Z",
  "account": {"account_id":"123-456-7890","account_name":"ACME Retail"},
  "date_range": {"start_date":"2025-07-01","end_date":"2025-07-31"},
  "totals": {"spend_usd":"50000.0","clicks":82000,"impressions":2100000,"conversions":"1200","revenue_usd":"240000.0"},
  "aggregates": {"match_type":{"broad_pct":0.52},"quality_score":{"p25":4.3}},
  "pmax": {"overlap_share":0.23,"delta_roas_vs_search":-0.18,"wasted_spend_overlap":"1300.0"},
  "conflicts": {"negatives_blocking_converters_count":2},
  "geo": {"low_cr_outliers_count":4,"savings_estimate":"900.0"},
  "findings": [
    {
      "id":"KW_BROAD_SHARE_HIGH",
      "category":"keywords",
      "summary":"Broad match dominates spend",
      "severity":"medium",
      "confidence":0.9,
      "entities":[{"type":"keyword","id":"kw_abc123","name":"+shoes"}],
      "dims":{"brand":"non_brand"},
      "metrics":{"broad_pct":0.52,"qs_p25":4.3},
      "evidence":[{"source":"google_ads.query","rows":2500,"checksum":"sha256:..."}],
      "provenance":{"name":"match_type_share","version":"0.5.1","git_sha":"abcde12"}
    }
  ],
  "index": {"top_broad_by_cost":["kw_abc123","kw_def456"]},
  "data_sources": [],
  "analyzers": [{"name":"match_type_share","version":"0.5.1","git_sha":"abcde12"}],
  "completeness":{"has_pmax_data":true,"tracking_ok":true}
}
```

---

## Common pitfalls (and how this IR avoids them)

* **Rules relying on ad-hoc dicts** → centralize in `aggregates`/`findings.metrics`.
* **Prose hiding facts** → the IR is *numbers only*, so you can verify them.
* **Model hallucination** → the writer cannot invent metrics; you validate against schema + cross-check against IR.
* **Upgrades breaking everything** → `schema_version` + pydantic validation + migration scripts.

