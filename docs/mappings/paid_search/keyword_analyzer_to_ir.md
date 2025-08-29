# Mapping Spec: PaidSearch KeywordAnalyzer → Core IR (AuditFindings)

Status: Draft
Owner: paid_search domain

Summary
Map outputs from PaidSearchNav KeywordAnalyzer to Core IR AuditFindings using Pydantic base types from PR #47.

Source examples
- Cotton Patch: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/cotton_patch/keywordanalyzer_20250824_180711.json
- Topgolf: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/topgolf/keywordanalyzer_20250824_122013.json

Input shape (observed)
- analyzer: "KeywordAnalyzer"
- customer_id: str
- analysis_period: { start_date: ISO datetime, end_date: ISO datetime }
- timestamp: ISO datetime
- summary: {
  total_keywords_analyzed: int,
  recommendations_count: int,
  potential_monthly_savings: number,
  priority_level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"
}
- detailed_findings:
  - underperforming_keywords: [ { name: str, match_type: BROAD|PHRASE|EXACT, cost: number, conversions: int, cpa: number|"N/A", campaign: str, recommendation: str } ]
  - top_performers: [ { name: str, match_type: BROAD|PHRASE|EXACT, cost: number, conversions: int, cpa: number, campaign: str, recommendation: str } ]
  - recommendations: [str]

IR target
- AuditFindings
  - account: AccountMeta(account_id = customer_id)
  - date_range: DateRange(start_date = date(analysis_period.start_date), end_date = date(analysis_period.end_date))
  - totals: Totals (if an overall cost exists, map to totals.spend/revenue; otherwise defaults)
  - aggregates: Optionally store summary under aggregates["keywords"]
  - findings: 1 Finding per item in underperforming_keywords + top_performers
  - data_sources + analyzers similar to other specs

Finding mapping
- category: keywords
- severity: map summary.priority_level → Severity (CRITICAL→high, etc.) or infer from item-level cpa/cost thresholds if desired
- summary: e.g., "Underperforming keyword 'restaurant near me' (BROAD)"
- description: item.recommendation
- entities: [
  { type: "keyword", id: f"kw:{name}", name },
  { type: "campaign", id: f"cmp:{campaign}", name: campaign }
]
- dims: { match_type, campaign }
- metrics: { cost, conversions, cpa? (omit if N/A) }
- evidence: { source: "paid_search_nav.keyword", rows: null, entities: [] }

Edge cases
- cpa == "N/A": omit or set to null; model validation prefers Decimal so omit is cleaner.
- costs: treat as Decimal; leave currency implicit (USD). Optionally name metrics cost_usd/cpa_usd for clarity.

Example IR finding
```json path=null start=null
{
  "id": "keyword_analyzer_cotton_patch_001_under_1_food_delivery",
  "category": "keywords",
  "summary": "Underperforming keyword 'food delivery' (BROAD)",
  "description": "Pause - Zero conversions after $892.45 spend",
  "severity": "high",
  "entities": [
    {"type": "keyword", "id": "kw:food delivery", "name": "food delivery"},
    {"type": "campaign", "id": "cmp:Cotton Patch - Generic Terms", "name": "Cotton Patch - Generic Terms"}
  ],
  "dims": {"match_type": "BROAD", "campaign": "Cotton Patch - Generic Terms"},
  "metrics": {"cost": 892.45, "conversions": 0},
  "evidence": {"source": "paid_search_nav.keyword", "rows": null, "entities": []}
}
```

Complete example AuditFindings output
```json path=null start=null
{
  "account": {"account_id": "cotton_patch_001"},
  "date_range": {
    "start_date": "2025-08-01",
    "end_date": "2025-08-24"
  },
  "totals": {},
  "aggregates": {
    "keywords": {
      "total_analyzed": 245,
      "recommendations_count": 18,
      "potential_monthly_savings": 3450.75,
      "priority_level": "HIGH"
    }
  },
  "findings": [
    {
      "id": "keyword_analyzer_cotton_patch_001_under_1_restaurant_near_me",
      "category": "keywords",
      "summary": "Underperforming keyword 'restaurant near me' (BROAD)",
      "description": "Pause - Zero conversions after $892.45 spend",
      "severity": "high",
      "entities": [
        {"type": "keyword", "id": "kw:restaurant near me", "name": "restaurant near me"},
        {"type": "campaign", "id": "cmp:Cotton Patch - Generic Terms", "name": "Cotton Patch - Generic Terms"}
      ],
      "dims": {"match_type": "BROAD", "campaign": "Cotton Patch - Generic Terms"},
      "metrics": {"cost": 892.45, "conversions": 0},
      "evidence": {"source": "paid_search_nav.keyword"}
    },
    {
      "id": "keyword_analyzer_cotton_patch_001_top_1_cotton_patch_cafe",
      "category": "keywords",
      "summary": "Top performing keyword 'cotton patch cafe menu' (EXACT)",
      "description": "Increase budget allocation - Strong ROI performance",
      "severity": "low",
      "entities": [
        {"type": "keyword", "id": "kw:cotton patch cafe menu", "name": "cotton patch cafe menu"},
        {"type": "campaign", "id": "cmp:Cotton Patch - Brand", "name": "Cotton Patch - Brand"}
      ],
      "dims": {"match_type": "EXACT", "campaign": "Cotton Patch - Brand"},
      "metrics": {"cost": 456.78, "conversions": 28, "cpa": 16.31},
      "evidence": {"source": "paid_search_nav.keyword"}
    }
  ],
  "data_sources": [
    {"source": "paid_search_nav.keyword"}
  ],
  "analyzers": [
    {
      "name": "KeywordAnalyzer",
      "version": "1.0.0",
      "finished_at": "2025-08-24T18:07:11"
    }
  ]
}
```

Acceptance criteria
- All items produce valid Finding objects; AuditFindings validates end-to-end
- N/A cpa handled gracefully (omitted)
- At least 1 underperformer and 1 top performer mapped in tests

Notes
- Match types are normalized to uppercase (BROAD, PHRASE, EXACT)
- Empty/null campaign names default to "Unknown Campaign"
- Empty/null keyword names default to "unknown" 
- CPA values of "N/A" are omitted from metrics
- Top performing keywords typically get low severity since they're performing well
- Finding IDs include customer_id, type (under/top), counter, and sanitized keyword name

