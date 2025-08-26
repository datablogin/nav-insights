# Mapping Spec: PaidSearch VideoCreative → Core IR (AuditFindings)

Status: Draft
Owner: paid_search domain

## Summary
Map outputs from PaidSearchNav VideoCreative analyzer to Core IR AuditFindings using Pydantic base types. Handles video creative performance analysis including creative asset performance, audience insights, and view-through metrics.

## Source examples
- Example customer: /Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/example_customer/video_creative_20250824_180711.json
- Test fixtures: tests/fixtures/video_creative_happy_path.json, tests/fixtures/video_creative_edge_case.json

## Input shape (observed)
- analyzer: "VideoCreative" 
- customer_id: str (e.g., Google Ads account)
- analysis_period: { start_date: ISO datetime, end_date: ISO datetime }
- timestamp: ISO datetime
- summary: {
  total_video_creatives: int,
  poor_performers_count: int,
  top_performers_count: int,
  total_video_spend_micros: int,
  average_view_rate: float [0..1],
  priority_level: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"
}
- detailed_findings:
  - poor_performers: [ { 
    creative_id: str, 
    creative_name: str, 
    video_duration_seconds: int,
    impressions: int,
    views: int, 
    view_rate: float [0..1],
    cost_micros: int,
    conversions: int,
    cpa_micros: int|null,
    campaign: str,
    ad_group: str,
    recommendation: str,
    performance_score: float [0..1]
  } ]
  - top_performers: [ { 
    creative_id: str,
    creative_name: str,
    video_duration_seconds: int,
    impressions: int,
    views: int,
    view_rate: float [0..1], 
    cost_micros: int,
    conversions: int,
    cpa_micros: int|null,
    campaign: str,
    ad_group: str,
    recommendation: str,
    performance_score: float [0..1]
  } ]
  - insights: [str]
  - recommendations: [str]

## IR target
- AuditFindings
  - account: AccountMeta(account_id = customer_id)
  - date_range: DateRange(start_date = date(analysis_period.start_date), end_date = date(analysis_period.end_date))
  - totals: Totals with video spend converted from micros to USD
  - aggregates: store high-level summary metrics under aggregates.video = {...}
  - findings: one Finding per poor_performers[] item and per top_performers[] item
  - data_sources: Evidence entry referencing the analyzer
  - analyzers: AnalyzerProvenance(name="VideoCreative", version=?, git_sha=?, started_at=?, finished_at=timestamp)

## Finding mapping
- category: creative
- severity: map summary.priority_level → Severity
  - CRITICAL→high; HIGH→high; MEDIUM→medium; LOW→low
- summary: "Poor video creative: {creative_name}" or "Top video creative: {creative_name}"
- description: source recommendation text
- entities: include creative as EntityRef(type="other", id=creative:{creative_id}, name=creative_name); include campaign and ad_group EntityRefs
- dims: store video_duration_seconds, campaign, ad_group, performance_score
- metrics (Decimal-compatible numerics): impressions, views, view_rate, cost_usd (converted from micros), conversions, cpa_usd (converted from micros, omit if null)
- evidence: Evidence(source="paid_search_nav.video_creative", entities=[creative_entity])

## Unit conversions
- cost_micros → cost_usd: divide by 1,000,000
- cpa_micros → cpa_usd: divide by 1,000,000, omit if null/N/A
- total_video_spend_micros → spend_usd: divide by 1,000,000

## Example IR finding (poor performer)
```json
{
  "category": "creative",
  "summary": "Poor video creative: Summer Sale 30s",
  "description": "Low view rate (12%) - consider shorter duration or more engaging opening",
  "severity": "high",
  "entities": [
    {"type": "other", "id": "creative:12345", "name": "Summer Sale 30s"},
    {"type": "campaign", "id": "cmp:Video Campaign", "name": "Video Campaign"},
    {"type": "ad_group", "id": "adg:Video Ad Group", "name": "Video Ad Group"}
  ],
  "dims": {
    "video_duration_seconds": 30,
    "campaign": "Video Campaign",
    "ad_group": "Video Ad Group",
    "performance_score": 0.12
  },
  "metrics": {
    "impressions": 45000,
    "views": 5400,
    "view_rate": 0.12,
    "cost_usd": 892.45,
    "conversions": 0,
    "performance_score": 0.12
  },
  "evidence": [
    {"source": "paid_search_nav.video_creative", "entities": []}
  ]
}
```

## Acceptance criteria
- Parse sample inputs into AuditFindings with ≥1 finding per poor_performer and per top_performer
- All required core fields validate via Pydantic; schema_version="1.0.0"
- Severity mapping documented and applied
- Currency values converted from micros to USD as Decimal numbers
- Unit tests covering:
  - happy-path mapping for poor and top performers
  - missing optional fields (cpa_micros handling)
  - enum fallbacks
  - micro-to-USD conversions

## Open questions / notes
- Video creative entities may benefit from a dedicated EntityType.creative in the future
- Performance scores and view rates provide rich creative optimization insights
- Consider adding video-specific aggregates for view-through metrics