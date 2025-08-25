# Mapping Spec: PaidSearch SearchTermsAnalyzer → Core IR (AuditFindings)

Status: Draft
Owner: paid_search domain

Summary
Map outputs from PaidSearchNav SearchTermsAnalyzer to Core IR AuditFindings using Pydantic base types from PR #47.

Source examples
- Cotton Patch: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/cotton_patch/searchtermsanalyzer_20250824_180711.json
- Topgolf: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/topgolf/searchtermsanalyzer_20250824_122013.json

Input shape (observed)
- analyzer: "SearchTermsAnalyzer"
- customer_id: str
- analysis_period: { start_date: ISO datetime, end_date: ISO datetime }
- timestamp: ISO datetime
- summary: {
  total_search_terms_analyzed: int,
  wasteful_terms_identified: int,
  recommendations_count: int,
  potential_monthly_savings: number,
  priority_level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"
}
- detailed_findings:
  - wasteful_search_terms: [ { term: str, cost: number, conversions: int, clicks: int, keyword_triggered: str, recommendation: str } ]
  - negative_keyword_suggestions: [ { negative_keyword: str, match_type: BROAD|PHRASE|EXACT, estimated_savings: number, reason: str } ]
  - recommendations: [str]

IR target
- AuditFindings
  - account: AccountMeta(account_id = customer_id)
  - date_range: DateRange(start_date = date(analysis_period.start_date), end_date = date(analysis_period.end_date))
  - findings: one Finding per wasteful_search_terms[] and per negative_keyword_suggestions[]
  - aggregates: optionally store summary under aggregates["search_terms"]

Finding mapping
- category: keywords (or structure depending on taxonomy; keywords is acceptable)
- severity: map summary.priority_level → Severity
- summary/description:
  - Wasteful term: "Wasteful search term '<term>' — add negative"
  - Suggestion: "Negative keyword suggestion '<negative_keyword>'"
- entities:
  - For wasteful term: {type:"search_term", id:"st:<term>", name: term}, keyword_triggered as {type:"keyword", id:"kw:<keyword_triggered>", name: keyword_triggered}
- dims:
  - For suggestions: match_type, reason
- metrics:
  - Wasteful term: cost, conversions, clicks
  - Suggestion: estimated_savings (as estimated_savings_usd Decimal)
- evidence:
  - source: "paid_search_nav.search_terms"

Example IR finding (wasteful term)
```json
{
  "category": "keywords",
  "summary": "Wasteful search term 'cotton patch jobs' — add negative",
  "description": "Add as exact negative keyword",
  "severity": "high",
  "entities": [
    {"type": "search_term", "id": "st:cotton patch jobs", "name": "cotton patch jobs"},
    {"type": "keyword", "id": "kw:cotton patch", "name": "cotton patch"}
  ],
  "dims": {},
  "metrics": {"cost": 1834.67, "conversions": 0, "clicks": 234}
}
```

Acceptance criteria
- Produce valid AuditFindings objects with a representative set of wasteful terms and suggestions
- Numeric amounts captured as Decimal-compatible numbers
- Unit tests: at least one wasteful term and one suggestion mapped; missing optional fields handled

Notes
- Consider normalizing or deduplicating repeated terms/keywords.

