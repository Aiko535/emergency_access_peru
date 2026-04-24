# emergency_access_peru
District-level emergency healthcare access analysis in Peru.

## Project structure

```
data/
  raw/          Original datasets (not modified)
  processed/    Cleaned and integrated outputs
docs/
  methodology.md   Full decisions log for all tasks
src/
  utils.py         Encoding detection, directory helpers
  data_loader.py   Raw dataset loaders (read-only)
  cleaning.py      Per-dataset cleaning functions (Task 1)
  geospatial.py    Spatial joins and district aggregation (Task 2)
run_cleaning.py    Task 1 orchestrator
run_geospatial.py  Task 2 orchestrator
```

## How to run

```bash
python run_cleaning.py      # Task 1: load, clean, save to data/processed/
python run_geospatial.py    # Task 2: spatial joins, district aggregation
```

Both scripts must be run from the project root with the virtual environment
active. Task 2 depends on Task 1 outputs.

---

## CRS handling

### Why two coordinate reference systems?

This project uses two CRS for different purposes, following the teacher's
convention from `docs/references/Geopandas1.ipynb`:

### EPSG:4326 — WGS84 (degrees)

Used for **storage, display, and spatial overlay**.

- All raw shapefiles (DISTRITOS, CCPP, IPRESS) arrive in EPSG:4326.
- All processed `.gpkg` outputs are stored in EPSG:4326.
- Point-in-polygon joins (`gpd.sjoin(..., predicate='within')`) run in
  EPSG:4326 because overlay correctness depends on consistent coordinates,
  not metric units.
- Folium maps require EPSG:4326.

### EPSG:32718 — WGS84 / UTM Zone 18S (metres)

Used exclusively for **distance and area calculations**.

- UTM Zone 18S covers mainland Peru with low distortion.
- `gpd.sjoin_nearest(..., distance_col='distance_m')` runs in EPSG:32718
  so that `distance_m` is in metres, not degrees.
- Any future area-based normalization (e.g., IPRESS per km²) must also
  use EPSG:32718.

### Where reprojection happens

| Operation | CRS used | Function |
|---|---|---|
| Load raw shapefiles | EPSG:4326 (as-is) | `data_loader.py` |
| Point-in-polygon district assignment | EPSG:4326 | `assign_ipress_to_districts`, `assign_ccpp_to_districts` |
| Nearest-IPRESS distance | EPSG:32718 | `nearest_ipress_per_ccpp` via `to_metric()` |
| Save all outputs | EPSG:4326 | `run_cleaning.py`, `run_geospatial.py` |
| Future: distance index component | EPSG:32718 | Task 3 |

Reprojection is performed with `gdf.to_crs("EPSG:32718")` inside
`to_metric()` and `gdf.to_crs("EPSG:4326")` inside `to_wgs84()` in
`src/geospatial.py`. The original GeoDataFrames are never modified in place;
reprojection returns a new object scoped to the function that needs it.

### Why not use a single CRS throughout?

Degree-based distances are non-uniform: one degree of longitude near Lima
(~12 S) is approximately 96 km, but this varies with latitude. Using
EPSG:4326 for `sjoin_nearest` would return distances in degrees that cannot
be directly converted to metres without introducing error. EPSG:32718
eliminates this issue for the Peruvian territory covered by this project.
