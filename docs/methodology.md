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

---

## Task 1 — Cleaning decisions (final)

### Teacher's conventions applied (from Geopandas1.ipynb)
- Use `chardet` to detect encoding before reading CSVs.
- Keep column names as-is (NORTE, ESTE, CAMAS, UBIGEO in uppercase).
- Use UBIGEO as master join key (cast to int).
- Rename IDDIST to UBIGEO in the districts shapefile.
- CRS: EPSG:4326 for display, EPSG:32718 for distance computations.
- NORTE = longitude, ESTE = latitude (preserve this "inverted" naming
  documented by the teacher).
- Use `gpd.points_from_xy(df.NORTE, df.ESTE)` (longitude first).
- Use `pd.merge(..., how="inner", on="UBIGEO")` and
  `gpd.overlay(points, polys, how="intersection")`.

### DISTRITOS.shp
- 1,873 districts, EPSG:4326, zero duplicates.
- Action: rename IDDIST → UBIGEO, cast to int, select relevant columns,
  save to `data/processed/distritos.gpkg`.

### IPRESS (20,819 rows → ~20,793 kept)
- 26 duplicates by "Código Único" → drop with `keep='first'`.
- Coordinate cleaning:
  - 12,863 rows have no NORTE/ESTE (kept for availability analysis,
    excluded from spatial analysis).
  - 3 rows have NORTE==0 or ESTE==0 → drop.
  - 0 additional out-of-Peru-bbox points.
  - Final: 7,953 rows with valid geometry.
- Two outputs:
  - `ipress_clean.parquet` (all 20,793 rows).
  - `ipress_geo.gpkg` (7,953 rows with geometry, CRS EPSG:4326).

### Emergencias 2025 (342,753 rows)
- 19,458 fully duplicated rows → drop with `drop_duplicates()`.
- ~16,206 rows share key (CO_IPRESS, MES, SEXO, EDAD) but differ in
  NRO_TOTAL_ATENCIONES: these are treated as partial resubmissions.
  Decision: group by key and SUM the attention counts. This preserves
  all reported activity.
- NE_0001 placeholders (~13% of rows) → convert to NaN in
  NRO_TOTAL_ATENCIONES and NRO_TOTAL_ATENDIDOS; these rows still count
  for facility presence but not for activity volume.
- Match with IPRESS catalog: 89.6% (545 CO_IPRESS newer than catalog).
  The 28,510 unmatched rows are kept — they still have valid UBIGEO for
  district-level aggregation.
- UBIGEO match with DISTRITOS: 98.98%. Drop the 12 unmatched UBIGEOs.
- Output: `emergencias_clean.parquet`.

### Centros Poblados CCPP_IGN100K.shp (136,587 features)
- Structural "duplicates": 60,037 IGN records overlap with 75,164 INEI
  records (same places, different catalogs).
- Decision: keep INEI source only (FUENTE == 'INEI') because its CÓDIGO
  prefix matches UBIGEO. This retains 75,164 representative features.
- 680 IGN records with 9-digit CÓDIGO are excluded from code-based joins
  (they are Puno-prefixed codes labeled as Ancash — IGN internal codes,
  not UBIGEO). If needed, they can be assigned to districts via spatial
  join using their geometry.
- The Y column has a known bug (Y=X in ~45% of rows) → ignore Y, use
  only `geometry` for spatial operations.
- Output: `centros_poblados.gpkg` (CRS EPSG:4326).

### Quantitative impact of cleaning decisions
| Dataset | Raw rows | After cleaning | % retained |
|---|---|---|---|
| DISTRITOS | 1,873 | 1,873 | 100% |
| IPRESS (all) | 20,819 | 20,793 | 99.9% |
| IPRESS (geo) | 20,819 | 7,953 | 38.2% |
| Emergencias | 342,753 | ~323,295 | 94.3% |
| Centros poblados (INEI only) | 136,587 | 75,164 | 55.0% |

