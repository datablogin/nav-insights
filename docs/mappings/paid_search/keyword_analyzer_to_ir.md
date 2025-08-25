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
  "category": "keywords",
  "summary": "Underperforming keyword 'food delivery' (BROAD)",
  "description": "Pause - Zero conversions after $800+ spend",
  "severity": "high",
  "entities": [
    {"type": "keyword", "id": "kw:food delivery", "name": "food delivery"},
    {"type": "campaign", "id": "cmp:Cotton Patch - Generic Terms", "name": "Cotton Patch - Generic Terms"}
  ],
  "dims": {"match_type": "BROAD"},
  "metrics": {"cost": 892.45, "conversions": 0}
}
```

Acceptance criteria
- All items produce valid Finding objects; AuditFindings validates end-to-end
- N/A cpa handled gracefully (omitted)
- At least 1 underperformer and 1 top performer mapped in tests

Notes
- Consider normalizing match_type values and/or adding a dims.match_type_category for analysis.

