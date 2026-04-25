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
- Remaining rows that share key (CO_IPRESS, ANHO, MES, SEXO, EDAD) but
  differ in NRO_TOTAL_ATENCIONES are treated as partial resubmissions.
  Decision: group by key and SUM the attention counts. This preserves
  all reported activity. The groupby collapsed more resubmissions than
  initially estimated (~15k additional beyond the 19k exact duplicates),
  yielding 307,703 rows rather than the preliminary estimate of ~323k.
- NE_0001 placeholders (~13% of rows) → convert to NaN in
  NRO_TOTAL_ATENCIONES and NRO_TOTAL_ATENDIDOS; these rows still count
  for facility presence but not for activity volume.
- Match with IPRESS catalog: 89.6% (545 CO_IPRESS newer than catalog).
  The 28,510 unmatched rows are kept — they still have valid UBIGEO for
  district-level aggregation.
- UBIGEO match with DISTRITOS: 98.98%. Drop the 12 unmatched UBIGEOs.
- Output: `emergencias_clean.parquet` (307,703 rows).

### Centros Poblados CCPP_IGN100K.shp (136,587 features)
- Structural "duplicates": 60,037 IGN records overlap with 75,164 INEI
  records (same places, different catalogs).
- Decision: keep INEI source only (FUENTE == 'INEI') because its CÓDIGO
  prefix matches UBIGEO. This retains 75,164 representative features.
- Of those 75,164 INEI records, 38,862 have null CÓDIGO. These are kept
  with UBIGEO = NaN (nullable Int64). Their district will be assigned in
  Task 2 via spatial join (point-in-polygon against DISTRITOS) rather than
  by code. Discarding them would eliminate 52% of INEI records, harming
  index component C (distance from populated centers to nearest IPRESS).
- 397 INEI records with 9-digit CÓDIGO are excluded from output (same
  IGN-internal prefix issue found in the full dataset). Final INEI output:
  75,164 − 397 = 74,767 rows.
- The Y column has a known bug (Y=X in ~45% of rows) → ignore Y, use
  only `geometry` for spatial operations.
- Output: `centros_poblados.gpkg` (CRS EPSG:4326, 74,767 rows).

### Quantitative impact of cleaning decisions (verified against run_cleaning.py output)
| Dataset | Raw rows | After cleaning | % retained |
|---|---|---|---|
| DISTRITOS | 1,873 | 1,873 | 100.0% |
| IPRESS (all) | 20,819 | 20,793 | 99.9% |
| IPRESS (geo) | 20,819 | 7,941 | 38.1% |
| Emergencias | 342,753 | 307,703 | 89.8% |
| Centros poblados (INEI only) | 136,587 | 74,767 | 54.7% |

---

## Implementation notes — key design decisions

### Robust column access
- In `clean_ipress`, "Código Único" is accessed by column index (`df.columns[1]`)
  rather than by name. The name contains a tilde that can decode differently
  across OS/encoding configurations.
- In `clean_ccpp`, the CÓDIGO column is detected by content (strings of 9-10
  digits) rather than by name, for the same reason.

### Function purity
- `clean_emergencias` accepts `valid_ubigeos` as a parameter instead of reading
  the district shapefile internally. This keeps the function pure and testable;
  the orchestrator (`run_cleaning.py`) is responsible for wiring inputs.

### Handling of "not reported" vs "reported zero"
- When aggregating emergency counts with `groupby.sum()`, we pass `min_count=1`.
  This ensures that a group with all-NaN values (no valid report) stays NaN,
  instead of being collapsed to 0. Zero reported emergencies and absence of
  a report are conceptually different and must not be conflated.

### Combined boolean masks
- IPRESS coordinate validation uses a single combined boolean mask (null-check,
  zero-check, bbox-check) instead of sequential filters. This is more readable
  and avoids silent bugs if a criterion is forgotten.

### Case normalization
- CCPP's `FUENTE` filter uses `.str.upper() == 'INEI'` to capture both 'INEI'
  and 'inei' variants present in the raw data.

### pandas 2.0 StringDtype compatibility
- In pandas 2.0+, string columns loaded via geopandas have dtype `StringDtype`
  rather than `object`. The condition `gdf[c].dtype == object` returns False for
  all string columns, causing `StopIteration` in the CÓDIGO column detector.
  Fixed by replacing the dtype check with `pd.api.types.is_string_dtype(gdf[c])`,
  which returns True for both `object` and `StringDtype`.

---

## Task 2 — Geospatial integration (final results)

### IPRESS district assignment
- `gpd.sjoin(how='left', predicate='within')` in EPSG:4326.
- **7,939 of 7,941** geolocated IPRESS matched to a district.
- 2 IPRESS fall outside every district polygon (coastal/boundary points);
  these retain `UBIGEO_district = NaN` and are excluded from spatial counts.
- Output: `ipress_with_district.gpkg`.

### CCPP district assignment
- Same `gpd.sjoin` approach applied to all 74,767 CCPP.
- The 38,862 records with `UBIGEO = NaN` (no CÓDIGO in the raw data) were
  fully resolved by the spatial join → **0 unassigned after Step 2**.
- **1,035 mismatches** detected between the code-derived UBIGEO (`CÓDIGO[:6]`)
  and the spatially-containing district. These are populated centers whose
  administrative code points to a different district than their geographic
  location. Code-based UBIGEO is kept as authoritative (emitted as a
  `UserWarning`, not an error). Represents 2.9% of code-holding records.
- Output: `ccpp_with_district.gpkg`.

### Nearest-IPRESS distances
- `gpd.sjoin_nearest()` in EPSG:32718 (metres) — Euclidean distance.
- Computed from every CCPP to the nearest IPRESS in the full geolocated set.
  (In Task 3, this will be rerun on the emergency-capable IPRESS subset.)
- Distance statistics across CCPP points:
  - Median: **3.3 km**
- Distance statistics aggregated to district level (mean per district):
  - Median across districts: **3.2 km**
  - p25 / p75: **2.2 km / 5.1 km**
  - Max: **115.1 km** (remote districts, likely Amazon/highlands)
- Output: `district_spatial_summary.{parquet,gpkg}`.

### District coverage gaps
| Gap | Districts | Notes |
|---|---|---|
| No IPRESS (administrative) | 14 | No facility reported in SUSALUD for that district |
| No IPRESS (geolocated) | 56 | Facility exists administratively but no verified coords |
| No CCPP assigned | 61 | No populated center assigned; may lack settlements or coords |

### Design decisions — Task 2
- **Two UBIGEO columns in ipress_with_district**: `UBIGEO` (administrative,
  from IPRESS catalogue) and `UBIGEO_district` (spatial). Keeping both allows
  downstream detection of facilities that are administratively attributed to
  a different district than where they are physically located.
- **GPKG round-trip coerces nullable Int64 → float64**: GPKG does not support
  nullable integer types. CCPP `UBIGEO` reloads as `float64`; all comparisons
  and casts account for this explicitly.
- **Only geometry travels to `sjoin_nearest`**: accented column names
  ('Código Único') can produce unexpected suffix collisions (`_left`/`_right`)
  in join results. Both GeoDataFrames are reduced to `[geometry]` before the
  join; the IPRESS code is re-attached under the alias `CODIGO_IPRESS`.
- **Deduplication after sjoin**: `~joined.index.duplicated(keep='first')`
  handles the rare edge case of a point lying exactly on a shared polygon
  boundary, which would otherwise produce duplicate rows.

---

## Task 3 -- District-level access index (final results)

### Emergency IPRESS flag
| Mode | Districts with >=1 emergency IPRESS |
|---|---|
| baseline (conservative) | 329 |
| alternative (permissive) | 467 |

The permissive mode adds 138 districts by including 24-hour facilities
without inpatient beds and hospitals regardless of schedule.

### Component C -- spatial distances
- Baseline median (district mean distance to nearest emergency IPRESS): **19.5 km**
- Alternative median: **15.8 km**

The 3.7 km reduction reflects the 138 additional emergency IPRESS in
the alternative mode, which are closer on average to previously
underserved districts.

### Index distributions (1,812 districts ranked; 61 excluded due to n_ccpp=0)

| Metric | Baseline (1/3,1/3,1/3) | Alternative (0.25,0.25,0.50) |
|---|---|---|
| Mean | 0.309 | 0.462 |
| Std | 0.033 | 0.042 |
| Min | 0.000 | 0.000 |
| Max | 0.733 | 0.781 |
| Top district (UBIGEO) | 40126 | 140101 |
| Bottom district (UBIGEO) | 160804 | 160110 |

**Baseline top**: UBIGEO 40126 -- highest emergency visit volume (B_norm=1.0)
combined with near-zero distance to emergency IPRESS (C_norm_inverted=0.999).

**Alternative top**: UBIGEO 140101 -- maximum facility availability
(A_norm=1.0) dominates under equal A/B weights; its already-high
C_norm_inverted (0.988) is further amplified by the 0.50 spatial weight.

**Bottom districts**: UBIGEO 160804 (baseline) and 160110 (alternative) --
zero emergency IPRESS, zero recorded attentions, and the worst spatial
access among all ranked districts (C_norm_inverted near 0).

### Sensitivity analysis
- 1,807 of 1,812 ranked districts change position between specifications.
- Maximum absolute rank change: **1,638 positions** (UBIGEO 180301: rank
  1,655 in baseline -> rank 17 in alternative).

**Interpretation**: The districts most sensitive to weight choice are those
with no local emergency IPRESS but geographically close to an emergency
IPRESS in a neighbouring district. Under the baseline (equal weights), the
absence of local facilities (A=0) and low activity (B~0) dominate, pushing
them toward the bottom. Under the alternative, the doubled spatial weight
(0.50) rewards their proximity, lifting them sharply in the ranking. This
pattern directly addresses the research question on methodological
sensitivity (Pregunta 4): conclusions about which districts are
"poorly served" are highly dependent on whether the index treats spatial
access as equivalent to facility presence and activity, or as the binding
constraint.

### Outputs
| File | Location |
|---|---|
| district_index_baseline.parquet | data/processed/ |
| district_index_alternative.parquet | data/processed/ |
| district_index_comparison.parquet | data/processed/ |
| top_bottom_10_districts_baseline.csv | output/tables/ |
| top_bottom_10_districts_alternative.csv | output/tables/ |
| rank_changes_top20.csv | output/tables/ |