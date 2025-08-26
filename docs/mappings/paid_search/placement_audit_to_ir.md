# Mapping Spec: PaidSearch PlacementAudit → Core IR (AuditFindings)

Status: Draft
Owner: paid_search domain

## Summary
Map outputs from PaidSearchNav PlacementAudit analyzer to Core IR AuditFindings using Pydantic base types from PR #47.

## Source examples
- Cotton Patch: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/cotton_patch/placement_audit_20250824_180711.json
- Topgolf: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/topgolf/placement_audit_20250824_122013.json

## Input shape (observed)
- analyzer: "placement_audit"
- customer_id: str
- analysis_period: { start_date: ISO datetime, end_date: ISO datetime }
- timestamp: ISO datetime
- summary: {
  total_placements_analyzed: int,
  poor_performing_placements: int,
  recommendations_count: int,
  potential_monthly_savings: number,
  priority_level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"
}
- detailed_findings:
  - poor_performers: [ { 
    placement_url: str, 
    network: "Display"|"YouTube"|"Gmail"|"Apps", 
    cost: number, 
    conversions: int, 
    clicks: int,
    impressions: int,
    ctr: number,
    conversion_rate: number,
    cpa: number|"N/A",
    campaign: str,
    ad_group: str,
    recommendation: str 
  } ]
  - top_performers: [ { 
    placement_url: str, 
    network: "Display"|"YouTube"|"Gmail"|"Apps", 
    cost: number, 
    conversions: int, 
    clicks: int,
    impressions: int,
    ctr: number,
    conversion_rate: number,
    cpa: number,
    campaign: str,
    ad_group: str,
    recommendation: str 
  } ]
  - recommendations: [str]

## IR target
- AuditFindings
  - account: AccountMeta(account_id = customer_id)
  - date_range: DateRange(start_date = date(analysis_period.start_date), end_date = date(analysis_period.end_date))
  - totals: Totals (aggregate totals from placement data if available, otherwise defaults)
  - aggregates: Store placement network distribution under aggregates["networks"]
  - findings: 1 Finding per item in poor_performers + top_performers
  - data_sources + analyzers similar to other specs

## Finding mapping
- category: "creative" (placements are part of creative/display optimization)
- severity: map summary.priority_level → Severity (CRITICAL→high, etc.) or infer from item-level performance metrics
- summary: e.g., "Poor performing placement 'example.com'" or "Top performing placement 'youtube.com'"
- description: item.recommendation
- entities: [
  { type: "placement", id: f"placement:{placement_url}", name: placement_url },
  { type: "campaign", id: f"cmp:{campaign}", name: campaign },
  { type: "ad_group", id: f"adg:{ad_group}", name: ad_group }
]
- dims: { network, campaign, ad_group }
- metrics: { 
  cost, 
  conversions, 
  clicks, 
  impressions, 
  ctr, 
  conversion_rate, 
  cpa? (omit if N/A) 
}
- evidence: { source: "paid_search_nav.placement_audit", rows: null, entities: [] }

## Unit conversions
- Cost amounts: treat as Decimal USD (no conversion needed if already in USD)
- Rates (CTR, conversion_rate): store as decimals in [0,1] range (convert percentages if needed)
- Counts (clicks, impressions, conversions): store as provided

## Edge cases
- cpa == "N/A": omit from metrics; model validation prefers Decimal so omission is cleaner
- Missing placement_url: use "unknown_placement" as fallback
- Zero impressions: handle division-by-zero gracefully in rate calculations
- Network normalization: standardize to ["Display", "YouTube", "Gmail", "Apps", "Search Partners"]

## Example IR finding (poor performer)
```json
{
  "id": "PLACEMENT_POOR_example.com",
  "category": "creative",
  "summary": "Poor performing placement 'example.com'",
  "description": "Exclude placement - High cost with zero conversions",
  "severity": "high",
  "confidence": 0.9,
  "entities": [
    {"type": "placement", "id": "placement:example.com", "name": "example.com"},
    {"type": "campaign", "id": "cmp:Display Campaign", "name": "Display Campaign"},
    {"type": "ad_group", "id": "adg:General Display", "name": "General Display"}
  ],
  "dims": {
    "network": "Display",
    "campaign": "Display Campaign", 
    "ad_group": "General Display"
  },
  "metrics": {
    "cost": 245.67,
    "conversions": 0,
    "clicks": 123,
    "impressions": 45678,
    "ctr": 0.0027,
    "conversion_rate": 0.0
  },
  "evidence": [
    {
      "source": "paid_search_nav.placement_audit",
      "query": null,
      "rows": null,
      "sample": [],
      "checksum": null,
      "entities": []
    }
  ]
}
```

## Acceptance criteria
- All placement items produce valid Finding objects; AuditFindings validates end-to-end
- N/A cpa handled gracefully (omitted from metrics)
- Network types normalized to standard values
- At least 1 poor performer and 1 top performer mapped in tests
- Rate values properly converted to [0,1] decimal range
- ≥2 sample fixtures validate against IR (happy-path + edge-case)

## Notes
- Consider adding placement categorization (e.g., mobile apps vs websites) as additional dims
- May want to aggregate network-level performance in aggregates["networks"] for rule evaluation
- Placement URLs should be validated/sanitized for security
