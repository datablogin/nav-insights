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
