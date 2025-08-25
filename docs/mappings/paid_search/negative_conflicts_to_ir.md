# Mapping Spec: PaidSearch NegativeConflicts → Core IR (AuditFindings)

**Status:** Draft  
**Owner:** paid_search domain  
**Issue:** #39

## Summary
Map outputs from PaidSearchNav negative_conflicts.py analyzer to Core IR AuditFindings using Pydantic base types. This analyzer identifies conflicts between negative keywords and converting search terms.

## Source Description
The `negative_conflicts.py` analyzer identifies situations where:
- Negative keywords are blocking potentially valuable search terms that have conversions
- Broad negative keywords are overly restrictive and eliminating profitable traffic
- Conflicting negative keyword strategies across campaigns/ad groups

## Input Shape (Expected)
```json
{
  "analyzer": "negative_conflicts",
  "customer_id": "string",
  "analysis_period": {
    "start_date": "ISO datetime",
    "end_date": "ISO datetime"
  },
  "timestamp": "ISO datetime",
  "summary": {
    "total_conflicts_found": "int",
    "blocked_conversions": "int", 
    "estimated_lost_revenue_usd": "number",
    "conflicted_negative_keywords": "int",
    "priority_level": "LOW|MEDIUM|HIGH|CRITICAL"
  },
  "detailed_findings": {
    "blocking_conflicts": [
      {
        "negative_keyword": "string",
        "match_type": "BROAD|PHRASE|EXACT",
        "blocked_search_term": "string",
        "conversions_lost": "int",
        "revenue_lost_usd": "number",
        "clicks_blocked": "int",
        "campaign_name": "string",
        "ad_group_name": "string",
        "recommendation": "string"
      }
    ],
    "overly_broad_negatives": [
      {
        "negative_keyword": "string", 
        "match_type": "BROAD|PHRASE|EXACT",
        "affected_search_terms_count": "int",
        "total_revenue_impact_usd": "number",
        "campaign_name": "string",
        "recommendation": "string"
      }
    ],
    "recommendations": ["string"]
  }
}
```

## IR Target Mapping

### Core AuditFindings Structure
- **account:** `AccountMeta(account_id = customer_id)`
- **date_range:** `DateRange(start_date = date(analysis_period.start_date), end_date = date(analysis_period.end_date))`
- **findings:** One `Finding` per blocking conflict and per overly broad negative
- **totals:** Aggregate revenue impact and conversion losses
- **conflicts:** Store summary metrics under `conflicts` namespace

### Finding Mapping

#### For Blocking Conflicts:
- **id:** `"NEG_CONFLICT_BLOCK_{index}"`
- **category:** `FindingCategory.conflicts`
- **severity:** Map from `summary.priority_level` → `Severity`
- **summary:** `"Negative keyword '{negative_keyword}' blocking converting term '{blocked_search_term}'"`
- **description:** Include recommendation text
- **entities:**
  - `{type: "keyword", id: "neg:{negative_keyword}", name: negative_keyword}` (negative keyword)
  - `{type: "search_term", id: "st:{blocked_search_term}", name: blocked_search_term}` (blocked term)
  - `{type: "campaign", id: "camp:{campaign_name}", name: campaign_name}`
  - `{type: "ad_group", id: "ag:{ad_group_name}", name: ad_group_name}`
- **dims:** `{match_type: match_type, conflict_type: "blocking"}`
- **metrics:** 
  - `conversions_lost: Decimal(conversions_lost)`
  - `revenue_lost_usd: Decimal(revenue_lost_usd)`
  - `clicks_blocked: Decimal(clicks_blocked)`

#### For Overly Broad Negatives:
- **id:** `"NEG_CONFLICT_BROAD_{index}"`
- **category:** `FindingCategory.conflicts`
- **severity:** Map from impact level
- **summary:** `"Overly broad negative '{negative_keyword}' affecting {affected_search_terms_count} terms"`
- **description:** Include recommendation text
- **entities:**
  - `{type: "keyword", id: "neg:{negative_keyword}", name: negative_keyword}` (broad negative)
  - `{type: "campaign", id: "camp:{campaign_name}", name: campaign_name}`
- **dims:** `{match_type: match_type, conflict_type: "overly_broad"}`
- **metrics:**
  - `affected_terms_count: Decimal(affected_search_terms_count)`
  - `total_revenue_impact_usd: Decimal(total_revenue_impact_usd)`

### Evidence Structure
- **source:** `"paid_search_nav.negative_conflicts"`
- **query:** Optional - could include filter criteria
- **rows:** Total conflicts found
- **entities:** List of all affected campaigns/ad groups

### Unit Conversions
- Revenue amounts: Convert from source currency to USD Decimal
- Counts: Convert to Decimal for consistency
- Match types: Normalize to uppercase enum values

## Example IR Finding (Blocking Conflict)
```json
{
  "id": "NEG_CONFLICT_BLOCK_001",
  "category": "conflicts",
  "summary": "Negative keyword 'free' blocking converting term 'free shipping'",
  "description": "Consider changing negative 'free' to phrase match or adding exception for 'free shipping' terms that convert well",
  "severity": "high",
  "confidence": 0.85,
  "entities": [
    {"type": "keyword", "id": "neg:free", "name": "free"},
    {"type": "search_term", "id": "st:free shipping", "name": "free shipping"},
    {"type": "campaign", "id": "camp:Brand Campaign", "name": "Brand Campaign"},
    {"type": "ad_group", "id": "ag:Core Brand", "name": "Core Brand"}
  ],
  "dims": {
    "match_type": "BROAD",
    "conflict_type": "blocking"
  },
  "metrics": {
    "conversions_lost": "12",
    "revenue_lost_usd": "2400.00", 
    "clicks_blocked": "45"
  },
  "evidence": [
    {
      "source": "paid_search_nav.negative_conflicts",
      "rows": 1,
      "entities": [
        {"type": "campaign", "id": "camp:Brand Campaign", "name": "Brand Campaign"}
      ]
    }
  ]
}
```

## Totals Integration
```json
{
  "totals": {
    "spend_usd": "0",  // Not applicable for this analyzer
    "revenue_usd": "170000.0",  // Total account revenue (positive)
    "conversions": "850.0"  // Total account conversions
  }
}
```

Note: Totals represent overall account performance. Individual finding metrics use positive values to represent lost opportunity amounts.

## Conflicts Namespace
```json
{
  "conflicts": {
    "negatives_blocking_converters_count": "7",
    "blocked_conversions_total": "28", 
    "revenue_impact_usd": "5600.00",
    "overly_broad_negatives_count": "3"
  }
}
```

## Acceptance Criteria
- [x] Mapping spec created under `domain/search` 
- [ ] Produce valid `AuditFindings` objects with representative conflicts
- [ ] ≥2 sample fixtures (happy-path + edge-case) validate against IR
- [ ] Numeric amounts captured as Decimal-compatible
- [ ] Unit tests validate fixture loading and key field semantics
- [ ] Coverage table entry added

## Test Strategy
- **Unit tests:** Load fixtures, assert Pydantic validation, verify totals alignment
- **Golden tests:** Ensure serialized IR for canonical input remains stable
- **Edge cases:** Handle missing optional fields, zero conflicts, extreme values

## Dependencies
- Core IR base types (Issue #3) ✅ 
- Epic #12 (analyzer integration)
- PaidSearchNav analyzer outputs

## Entity Structure Guidelines

### Entity `extra` vs `dims` Usage
- **Entity `extra`**: Use for entity-specific metadata that describes the entity itself
  - Example: `{"match_type": "BROAD"}` for a keyword entity
  - Purpose: Provides context about the entity that may not be captured in standard fields
- **Finding `dims`**: Use for finding-level dimensions that categorize the finding
  - Example: `{"match_type": "BROAD", "conflict_type": "blocking"}`
  - Purpose: Enables filtering and grouping of findings by analytical dimensions

### Revenue Sign Convention
- **Positive values** in `revenue_lost_usd` and similar metrics represent lost opportunity
- **Negative values** in totals represent actual negative impact on account performance
- This distinction allows for clear separation between individual finding impacts and aggregate account-level effects

### Confidence Score Calculation
Confidence scores (0.0-1.0) are calculated based on:
- **Data volume**: Higher volume = higher confidence
- **Statistical significance**: Conversion rates and sample sizes
- **Temporal stability**: Consistent patterns over time
- **Account context**: Mature accounts vs new accounts

Typical ranges:
- `0.9+`: High-volume, statistically significant conflicts
- `0.7-0.9`: Moderate volume with clear patterns
- `0.5-0.7`: Lower volume but consistent impact
- `<0.5`: Minimal data, uncertain assessment (edge cases)

## Notes
- Consider conflict severity based on revenue impact thresholds
- May need to deduplicate conflicts across multiple campaigns
- Broad negative detection logic may vary by analyzer implementation