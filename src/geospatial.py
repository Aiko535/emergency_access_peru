"""Geospatial integration — CRS helpers, spatial joins, district aggregation.

CRS convention (from teacher's Geopandas1.ipynb):
  EPSG:4326  (WGS84, degrees) — default for storage, display and overlay.
  EPSG:32718 (UTM zone 18S, metres) — used only when measuring distances or areas.
"""

import warnings

import pandas as pd
import geopandas as gpd

_CRS_WGS84  = "EPSG:4326"
_CRS_METRIC = "EPSG:32718"   # WGS84 / UTM zone 18S — covers mainland Peru


# ─────────────────────────────────────────────────────────────────────────────
# CRS helpers
# ─────────────────────────────────────────────────────────────────────────────

def to_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject to EPSG:32718 (UTM 18S, metres) for distance/area calculations."""
    return gdf.to_crs(_CRS_METRIC)


def to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject to EPSG:4326 (WGS84, degrees) for display and overlay."""
    return gdf.to_crs(_CRS_WGS84)


# ─────────────────────────────────────────────────────────────────────────────
# District assignment — IPRESS
# ─────────────────────────────────────────────────────────────────────────────

def assign_ipress_to_districts(
    ipress_geo: gpd.GeoDataFrame,
    distritos: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Add UBIGEO_district to each IPRESS point via point-in-polygon join.

    Uses gpd.sjoin(how='left', predicate='within') in EPSG:4326.
    The original UBIGEO column (administrative, from the IPRESS catalogue) is
    preserved alongside UBIGEO_district (spatial). IPRESS that fall outside
    every district polygon receive UBIGEO_district = NaN.
    """
    dist = (
        distritos[["UBIGEO", "geometry"]]
        .rename(columns={"UBIGEO": "UBIGEO_district"})
    )
    joined = gpd.sjoin(ipress_geo, dist, how="left", predicate="within")

    # Drop sjoin bookkeeping column and deduplicate (boundary edge cases)
    joined = joined.drop(columns=["index_right"])
    joined = joined[~joined.index.duplicated(keep="first")]

    # Cast to nullable int for clarity; NaN is preserved for unmatched points
    joined["UBIGEO_district"] = joined["UBIGEO_district"].astype("Int64")
    return joined


# ─────────────────────────────────────────────────────────────────────────────
# District assignment — Centros Poblados
# ─────────────────────────────────────────────────────────────────────────────

def assign_ccpp_to_districts(
    ccpp: gpd.GeoDataFrame,
    distritos: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Fill and validate district assignment for all populated-center points.

    Workflow
    --------
    1. Spatially join every CCPP point against district polygons (EPSG:4326).
    2. For the ~35,905 records that already have UBIGEO from CÓDIGO[:6]:
       compare against the spatial result and warn on mismatches (code-based
       UBIGEO is kept as authoritative).
    3. For the ~38,862 records with UBIGEO = NaN: fill from the spatial result.

    Points that fall outside every district polygon (coastal, boundary edge
    cases) retain UBIGEO = NaN after this step.

    Note: CCPP UBIGEO is float64 after the GPKG round-trip (GPKG does not
    support nullable integers; NaN coerces int to float on reload).
    """
    dist = (
        distritos[["UBIGEO", "geometry"]]
        .rename(columns={"UBIGEO": "UBIGEO_sjoin"})
    )
    joined = gpd.sjoin(ccpp, dist, how="left", predicate="within")
    joined = joined.drop(columns=["index_right"])
    joined = joined[~joined.index.duplicated(keep="first")]

    # ── Validate code-based UBIGEO against spatial result ────────────────────
    # Both columns are float64: UBIGEO from gpkg round-trip, UBIGEO_sjoin from
    # sjoin NaN coercion. Integer-valued floats compare exactly.
    has_both = joined["UBIGEO"].notna() & joined["UBIGEO_sjoin"].notna()
    mismatch = has_both & (joined["UBIGEO"] != joined["UBIGEO_sjoin"])
    n_mismatch = int(mismatch.sum())
    if n_mismatch:
        warnings.warn(
            f"{n_mismatch:,} CCPP records have a code-derived UBIGEO (from CÓDIGO[:6]) "
            f"that differs from their spatially-containing district. "
            f"Code-based UBIGEO is kept as authoritative.",
            UserWarning,
            stacklevel=2,
        )

    # ── Fill NaN UBIGEO with spatial result ───────────────────────────────────
    joined["UBIGEO"] = joined["UBIGEO"].fillna(joined["UBIGEO_sjoin"])
    joined = joined.drop(columns=["UBIGEO_sjoin"])

    return joined


# ─────────────────────────────────────────────────────────────────────────────
# Nearest-IPRESS distance
# ─────────────────────────────────────────────────────────────────────────────

def nearest_ipress_per_ccpp(
    ccpp: gpd.GeoDataFrame,
    ipress_geo: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Find the nearest IPRESS for every populated-center point.

    Both inputs are reprojected to EPSG:32718 (metres) before the search so
    that distance_m is in metric units. Returns a plain DataFrame keyed by the
    original ccpp index — not a GeoDataFrame — for easy merging downstream.

    Parameters
    ----------
    ccpp : GeoDataFrame
        Populated centers (any subset). Its integer index is the join key.
    ipress_geo : GeoDataFrame
        IPRESS with geometry. Pass a filtered subset (e.g., only those with
        confirmed emergency services) to compute component-C distances.
        Accepts the full set for exploratory aggregations.

    Returns
    -------
    DataFrame with columns:
        ccpp_index            – original index value from *ccpp*
        nearest_ipress_codigo – Código Único of the nearest IPRESS
        distance_m            – Euclidean distance in metres (EPSG:32718)
    """
    # Only geometry travels to the join to avoid encoding issues with accented
    # column names ('Código Único') producing unexpected suffix behaviour.
    ccpp_m = to_metric(ccpp[["geometry"]].copy())

    # Alias 'Código Único' (column index 1) to a clean name before the join.
    codigo_col = ipress_geo.columns[1]
    ipress_m = to_metric(ipress_geo[["geometry"]].copy())
    ipress_m["CODIGO_IPRESS"] = ipress_geo[codigo_col].values

    result = gpd.sjoin_nearest(
        ccpp_m,
        ipress_m[["CODIGO_IPRESS", "geometry"]],
        how="left",
        distance_col="distance_m",
    )

    return pd.DataFrame({
        "ccpp_index":            result.index,
        "nearest_ipress_codigo": result["CODIGO_IPRESS"],
        "distance_m":            result["distance_m"],
    }).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# District-level aggregation
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_to_district(
    ipress_geo: gpd.GeoDataFrame,
    ipress_all: pd.DataFrame,
    ccpp: gpd.GeoDataFrame,
    distritos: gpd.GeoDataFrame,
    nearest_df: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """Aggregate IPRESS counts and CCPP distances to the district level.

    Parameters
    ----------
    ipress_geo : GeoDataFrame
        Output of assign_ipress_to_districts — must contain UBIGEO_district.
    ipress_all : DataFrame
        All IPRESS (with and without coordinates) — must contain UBIGEO (int).
    ccpp : GeoDataFrame
        Output of assign_ccpp_to_districts — UBIGEO column is float64.
    distritos : GeoDataFrame
        Cleaned district polygons — must contain UBIGEO (int) and geometry.
    nearest_df : DataFrame
        Output of nearest_ipress_per_ccpp — must contain ccpp_index, distance_m.

    Returns
    -------
    GeoDataFrame with one row per district and columns:
        UBIGEO, geometry,
        n_ipress_total             – all IPRESS administratively in district
        n_ipress_geo               – geolocated IPRESS spatially in district
        n_ccpp                     – populated centers assigned to district
        mean_dist_nearest_ipress_m – mean Euclidean distance (m) to nearest IPRESS
    """
    # ── n_ipress_total: code-based count, includes IPRESS without coordinates
    n_total = (
        ipress_all
        .groupby("UBIGEO")
        .size()
        .rename("n_ipress_total")
        .reset_index()
    )

    # ── n_ipress_geo: spatially-assigned geolocated IPRESS
    n_geo = (
        ipress_geo[ipress_geo["UBIGEO_district"].notna()]
        .groupby("UBIGEO_district")
        .size()
        .rename("n_ipress_geo")
        .reset_index()
        .rename(columns={"UBIGEO_district": "UBIGEO"})
    )
    n_geo["UBIGEO"] = n_geo["UBIGEO"].astype(int)

    # ── n_ccpp: populated centers with a valid district assignment
    n_ccpp_agg = (
        ccpp[ccpp["UBIGEO"].notna()]
        .groupby("UBIGEO")
        .size()
        .rename("n_ccpp")
        .reset_index()
    )
    n_ccpp_agg["UBIGEO"] = n_ccpp_agg["UBIGEO"].astype(int)

    # ── mean_dist: join nearest_df to ccpp by index, then aggregate by district
    ccpp_dist = ccpp[["UBIGEO"]].join(
        nearest_df.set_index("ccpp_index")["distance_m"]
    )
    mean_dist = (
        ccpp_dist[ccpp_dist["UBIGEO"].notna()]
        .groupby("UBIGEO")["distance_m"]
        .mean()
        .rename("mean_dist_nearest_ipress_m")
        .reset_index()
    )
    mean_dist["UBIGEO"] = mean_dist["UBIGEO"].astype(int)

    # ── Assemble: full district list, left-merge each aggregate
    result = distritos[["UBIGEO", "geometry"]].copy()
    for df in [n_total, n_geo, n_ccpp_agg, mean_dist]:
        result = result.merge(df, on="UBIGEO", how="left")

    # Districts with zero IPRESS / CCPP should show 0, not NaN
    for col in ("n_ipress_total", "n_ipress_geo", "n_ccpp"):
        result[col] = result[col].fillna(0).astype(int)

    return result
