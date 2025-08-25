# Mapping Spec: PaidSearch CompetitorInsightsAnalyzer → Core IR (AuditFindings)

Status: Draft
Owner: paid_search domain

Summary
Map outputs from PaidSearchNav CompetitorInsightsAnalyzer to Core IR AuditFindings using Pydantic base types from PR #47.

Source examples
- Cotton Patch: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/cotton_patch/competitorinsightsanalyzer_20250824_180711.json
- Topgolf: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/topgolf/competitorinsightsanalyzer_20250824_122013.json

Input shape (observed)
- analyzer: "CompetitorInsightsAnalyzer"
- customer_id: str (e.g., Google Ads account)
- analysis_period: { start_date: ISO datetime, end_date: ISO datetime }
- timestamp: ISO datetime
- summary: {
  competitors_identified: int,
  auction_insights_analyzed: bool,
  keyword_overlap_detected: int,
  opportunity_score: float,
  potential_monthly_savings: number,
  priority_level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"
}
- detailed_findings:
  - primary_competitors: [ { competitor: str, impression_share_overlap: float [0..1], average_position_vs_you: float, shared_keywords: int, cost_competition_level: LOW|MEDIUM|HIGH, opportunity: str, monthly_search_volume: int, competitive_threat_level: LOW|MEDIUM|HIGH } ]
  - keyword_gaps: [ { keyword: str, competitor_using: [str], search_volume: int, competition: LOW|MEDIUM|HIGH, estimated_cpc: float, recommendation: str } ]
  - competitive_advantages: [str]
  - recommendations: [str]

IR target
- AuditFindings
  - account: AccountMeta(account_id = customer_id)
  - date_range: DateRange(start_date = date(analysis_period.start_date), end_date = date(analysis_period.end_date))
  - totals: Totals (optional aggregate spend if available; otherwise leave defaults)
  - aggregates: store high-level summary metrics optionally under aggregates["competition"] = {...}
  - findings: one Finding per primary_competitors[] item and per keyword_gaps[] item
  - data_sources: Evidence entry referencing the analyzer
  - analyzers: AnalyzerProvenance(name="CompetitorInsightsAnalyzer", version=?, git_sha=?, started_at=?, finished_at=timestamp)

Finding mapping
- category: competition (fallback to other until enum includes competition)
- severity: map summary.priority_level → Severity
  - CRITICAL→high (or add Severity.critical later); HIGH→high; MEDIUM→medium; LOW→low
- summary: short synopsis per item (see examples)
- description: source recommendation or opportunity text
- entities: include competitor as EntityRef(type="other" or "competitor", name=competitor); include keyword EntityRef for keyword_gaps
- dims: store tags such as cost_competition_level, competitive_threat_level, competition, competitor list for gaps
- metrics (Decimal-compatible numerics): impression_share_overlap, average_position_vs_you, shared_keywords, monthly_search_volume, opportunity_score, estimated_cpc, search_volume
- evidence: Evidence(source="paid_search_nav.competitor_insights", query="", rows=?, sample=[])

Example IR finding (keyword gap)
```json path=null start=null
{
  "category": "competition",
  "summary": "Gap: 'cracker barrel alternative' used by 2 competitors",
  "description": "Add as phrase match - high opportunity",
  "severity": "medium",
  "entities": [
    {"type": "other", "id": "competitor:Dennys", "name": "Denny's"},
    {"type": "other", "id": "competitor:IHOP", "name": "IHOP"},
    {"type": "keyword", "id": "kw:cracker barrel alternative", "name": "cracker barrel alternative"}
  ],
  "dims": {
    "competition": "MEDIUM"
  },
  "metrics": {
    "search_volume": 2400,
    "estimated_cpc": 1.85
  },
  "evidence": [
    {"source": "paid_search_nav.competitor_insights", "rows": null, "entities": []}
  ]
}
```

Acceptance criteria
- Parse sample files above into AuditFindings with ≥ 1 finding per primary_competitor and per keyword_gap
- All required core fields validate via Pydantic; schema_version="1.0.0"
- Severity mapping documented and applied
- Currency values (if any) represented as Decimal numbers in metrics (e.g., estimated_cpc)
- Unit tests covering:
  - happy-path mapping for competitor and gap
  - missing optional fields
  - enum fallbacks (competition category)

Open questions / notes
- Consider adding FindingCategory.competition and EntityType.competitor for clarity.
- If future CPC reported in different currencies, convert or include as *_usd metrics consistently.

