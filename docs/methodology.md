# Methodology — Emergency Healthcare Access Index

## Research question
Which districts in Peru appear relatively better or worse served in
emergency healthcare access, and what evidence supports that conclusion?

## Scope
- Geographic unit of analysis: district (distrito).
- Development phase: Lima Metropolitana (~43 districts) for fast iteration.
- Final phase: all Peruvian districts (~1874).

## Datasets
1. IPRESS (MINSA) — health facilities with coordinates.
2. Emergency care production (SUSALUD) — emergency visits per IPRESS.
3. Populated centers (IGN) — settlements with coordinates (CCPP_IGN100K).
4. District boundaries — shapefile with polygons (DISTRITOS).

## Index components

### A. Facility availability
IPRESS offering emergency services per 10,000 district inhabitants.
Rationale: captures theoretical supply adjusted for population.
Limitation: does not account for facility complexity/capacity.

### B. Emergency activity
Emergency visits per 10,000 district inhabitants (most recent full year).
Rationale: a facility that exists but does not produce attentions
is not functionally available; this captures real operation.
Limitation: high activity may reflect saturation, not quality.

### C. Spatial access from populated centers
Mean distance (km) from each populated center in the district to the
nearest IPRESS offering emergency services.
Rationale: two districts with the same facility count can have very
different accessibility depending on settlement distribution.
Limitation: Euclidean distance ignores terrain and road networks.

## Baseline index
Index = (1/3) * A_norm + (1/3) * B_norm + (1/3) * (1 - C_norm)
- All components are min-max normalized to [0, 1].
- C is inverted because greater distance means worse access.
- Higher index = better access. Range: [0, 1].

## Alternative specification
Index_alt = 0.25 * A_norm + 0.25 * B_norm + 0.50 * (1 - C_norm)
Rationale: in rural Peru, spatial access is often the binding constraint.
This weighting tests whether conclusions are robust to emphasizing geography.

## Sensitivity analysis
Districts are ranked under both specifications. Those with large rank
changes identify cases where conclusions depend on methodological choices.

## Known limitations
- Euclidean distance (no road networks).
- District-level population figures needed; source TBD from INEI.
- Emergency activity attributable only to IPRESS that report to SUSALUD.
- CRS selection affects distance calculations (see geospatial.py).

---

## Decision: emergencias year selection

Compared ConsultaC1_2024_v22.csv vs ConsultaC1_2025_v20.csv from SUSALUD.

| Metric | 2024 | 2025 |
|---|---|---|
| Total rows | 250,000 | 342,753 |
| Raw lines in file | 250,001 | 342,754 |
| Unique IPRESS (CO_IPRESS) | 4,293 | 5,245 |
| Rows with numeric attentions | 85.4% | 86.9% |
| Rows with NE_0001 placeholder | 14.6% | 13.1% |
| Months covered | 12 | 12 |
| Departments covered | 25 | 25 |
| Sum of attentions | 19.8 M | 20.7 M |

### Decision: use 2025.

Reasoning:
1. The 2024 file shows exactly 250,000 rows, a round number that suggests
   export truncation by the SUSALUD portal. The 2025 file has 342,753
   rows (non-round), consistent with full data export.
2. 2025 has more unique IPRESS reporting (5,245 vs 4,293), implying
   broader coverage of Peru's health facility network.
3. 2025 has a lower share of NE_0001 placeholders (13.1% vs 14.6%),
   indicating higher reporting completeness.
4. Monthly distribution in 2025 is uniform and slightly increasing,
   typical of a fully-closed year; 2024 distribution is flatter and
   may reflect the truncation artifact.

### Data quality note
In both files, ~14% of rows contain "NE_0001" in NRO_TOTAL_ATENCIONES
and related fields. These represent reporting facilities that did not
specify patient counts. They are kept for facility-presence analysis
(component A) but excluded from activity calculations (component B).