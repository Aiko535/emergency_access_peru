"""District-level metrics: emergency flag, index components, composite index.

Component definitions (from docs/methodology.md):
  A  Facility availability — emergency IPRESS per populated centre (proxy pop.)
  B  Emergency activity    — recorded emergency visits per populated centre
  C  Spatial access        — mean Euclidean distance (km) to nearest emergency
                             IPRESS, inverted so smaller distance = higher score

Index formula:
  index = wA * A_norm + wB * B_norm + wC * C_norm_inverted   (range [0, 1])

Baseline spec:    weights = (1/3, 1/3, 1/3),   flag mode = 'baseline'
Alternative spec: weights = (0.25, 0.25, 0.50), flag mode = 'alternative'

Districts with n_ccpp == 0 receive NaN for all components and are excluded
from the ranking. Their UBIGEO is listed explicitly in the output.
"""

import numpy as np
import pandas as pd
import geopandas as gpd

from src.geospatial import nearest_ipress_per_ccpp


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_col(df: pd.DataFrame, partial: str) -> str:
    """Return the best column match for *partial* (case-insensitive).

    Prefers exact match before falling back to substring. This prevents
    'Tipo' from matching 'Tipo Doc.Categorizacion' and similar collisions
    that arise from accented column names decoded differently per environment.
    """
    lower = partial.lower()
    exact = [c for c in df.columns if c.lower() == lower]
    if exact:
        return exact[0]
    partial_match = [c for c in df.columns if lower in c.lower()]
    if partial_match:
        return partial_match[0]
    raise KeyError(f"No column matching {partial!r} found in DataFrame.")


def _minmax(series: pd.Series) -> pd.Series:
    """Min-max normalisation to [0, 1]. NaN inputs remain NaN in output.

    Edge cases:
      All NaN        -> return series unchanged (all NaN).
      All same value -> return 0.0 for non-NaN rows (no discriminating power).
    """
    lo, hi = series.min(), series.max()
    if pd.isna(lo):
        return series.copy()
    if lo == hi:
        return pd.Series(
            np.where(series.notna(), 0.0, np.nan),
            index=series.index,
            dtype=float,
        )
    return (series - lo) / (hi - lo)


# ─────────────────────────────────────────────────────────────────────────────
# Emergency flag
# ─────────────────────────────────────────────────────────────────────────────

def flag_tiene_emergencia(
    ipress_df: pd.DataFrame,
    mode: str = "baseline",
) -> pd.Series:
    """Return a boolean Series indicating emergency-capable IPRESS.

    Pre-filter (applied before mode logic):
      Estado == 'ACTIVADO' AND Condicion == 'EN FUNCIONAMIENTO'.
      The 17 INOPERATIVO facilities are excluded regardless of Horario.

    Parameters
    ----------
    ipress_df : DataFrame
        IPRESS catalogue (ipress_clean.parquet or ipress_with_district.gpkg).
    mode : {'baseline', 'alternative'}
        'baseline'    -- conservative:
            Horario contains 'EMER'
            OR (Horario == '24 HORAS' AND Tipo contains 'CON INTERNAMIENTO').
        'alternative' -- permissive: baseline criteria PLUS
            OR Horario == '24 HORAS' (unconditional, any facility type)
            OR Clasificacion contains 'HOSPITAL'.

    Returns
    -------
    pd.Series of bool, same index as ipress_df.
    """
    if mode not in ("baseline", "alternative"):
        raise ValueError(f"mode must be 'baseline' or 'alternative', got {mode!r}")

    horario = ipress_df[_find_col(ipress_df, "Horario")].astype(str).str.upper()
    tipo    = ipress_df[_find_col(ipress_df, "Tipo")].astype(str).str.upper()
    clas    = ipress_df[_find_col(ipress_df, "Clasificaci")].astype(str).str.upper()
    estado  = ipress_df[_find_col(ipress_df, "Estado")].astype(str).str.upper()
    cond    = ipress_df[_find_col(ipress_df, "Condici")].astype(str).str.upper()

    # Pre-filter: active and operational only
    active = (estado == "ACTIVADO") & cond.str.contains("EN FUNCIONAMIENTO", na=False)

    # Core criteria shared by both modes
    emer_in_horario = horario.str.contains("EMER", na=False)
    h24_with_beds   = (horario == "24 HORAS") & tipo.str.contains("CON INTERNAMIENTO", na=False)
    baseline_core   = emer_in_horario | h24_with_beds

    if mode == "baseline":
        flag = active & baseline_core
    else:
        hospital_in_clas = clas.str.contains("HOSPITAL", na=False)
        flag = active & (baseline_core | (horario == "24 HORAS") | hospital_in_clas)

    return flag.rename("tiene_emergencia")


# ─────────────────────────────────────────────────────────────────────────────
# Component A -- Facility availability
# ─────────────────────────────────────────────────────────────────────────────

def compute_component_A(
    ipress_with_district: gpd.GeoDataFrame,
    distritos: gpd.GeoDataFrame,
    n_ccpp: pd.Series,
    mode: str = "baseline",
) -> pd.DataFrame:
    """Compute component A: emergency IPRESS per populated centre (proxy pop.).

    A_raw  = n_ipress_emergencia / n_ccpp
    A_norm = min-max normalisation of A_raw across all districts.

    Uses UBIGEO_district (spatially-verified) from ipress_with_district,
    not the administrative UBIGEO from the catalogue. UBIGEO_district is
    float64 after GPKG round-trip; cast to int after groupby.

    Parameters
    ----------
    ipress_with_district : GeoDataFrame
        Output of assign_ipress_to_districts. Must contain UBIGEO_district.
    distritos : GeoDataFrame
        Cleaned district polygons with UBIGEO (int) -- master district list.
    n_ccpp : Series indexed by UBIGEO (int)
        Count of assigned populated centres per district.
        Pass district_spatial_summary.set_index('UBIGEO')['n_ccpp'].
    mode : str
        Emergency-flag mode passed to flag_tiene_emergencia.

    Returns
    -------
    DataFrame [UBIGEO, n_ccpp, n_ipress_emergencia, A_raw, A_norm]
    """
    flag  = flag_tiene_emergencia(ipress_with_district, mode=mode)
    emerg = ipress_with_district[
        flag & ipress_with_district["UBIGEO_district"].notna()
    ]

    n_emerg = (
        emerg.groupby("UBIGEO_district")
        .size()
        .rename("n_ipress_emergencia")
        .reset_index()
        .rename(columns={"UBIGEO_district": "UBIGEO"})
    )
    n_emerg["UBIGEO"] = n_emerg["UBIGEO"].astype(int)

    result = distritos[["UBIGEO"]].copy()
    result = result.merge(n_emerg, on="UBIGEO", how="left")
    result["n_ipress_emergencia"] = result["n_ipress_emergencia"].fillna(0).astype(int)

    result = result.merge(
        n_ccpp.rename("n_ccpp").reset_index(), on="UBIGEO", how="left"
    )

    # n_ccpp == 0 -> NaN so division yields NaN (not inf); excluded from ranking
    result["A_raw"]  = result["n_ipress_emergencia"] / result["n_ccpp"].replace(0, np.nan)
    result["A_norm"] = _minmax(result["A_raw"])

    return result[["UBIGEO", "n_ccpp", "n_ipress_emergencia", "A_raw", "A_norm"]]


# ─────────────────────────────────────────────────────────────────────────────
# Component B -- Emergency activity
# ─────────────────────────────────────────────────────────────────────────────

def compute_component_B(
    emergencias: pd.DataFrame,
    distritos: gpd.GeoDataFrame,
    n_ccpp: pd.Series,
) -> pd.DataFrame:
    """Compute component B: emergency visit volume per populated centre.

    B_raw  = total_atenciones / n_ccpp
    B_norm = min-max normalisation of B_raw.

    NaN in NRO_TOTAL_ATENCIONES (former NE_0001 placeholders) contributes 0
    to the district sum (pandas .sum() default: skipna=True). A facility that
    reported presence but no numeric count is treated as zero activity -- it
    does not inflate nor deflate the district total.

    Component B does not depend on the emergency flag mode: total recorded
    emergency visits per district is the same regardless of IPRESS definition.
    Districts with n_ccpp == 0 receive B_raw = NaN.

    Returns
    -------
    DataFrame [UBIGEO, total_atenciones, B_raw, B_norm]
    """
    total = (
        emergencias.groupby("UBIGEO")["NRO_TOTAL_ATENCIONES"]
        .sum()
        .rename("total_atenciones")
        .reset_index()
    )

    result = distritos[["UBIGEO"]].copy()
    result = result.merge(total, on="UBIGEO", how="left")
    result["total_atenciones"] = result["total_atenciones"].fillna(0)

    result = result.merge(
        n_ccpp.rename("n_ccpp").reset_index(), on="UBIGEO", how="left"
    )

    result["B_raw"]  = result["total_atenciones"] / result["n_ccpp"].replace(0, np.nan)
    result["B_norm"] = _minmax(result["B_raw"])

    return result[["UBIGEO", "total_atenciones", "B_raw", "B_norm"]]


# ─────────────────────────────────────────────────────────────────────────────
# Component C -- Spatial access
# ─────────────────────────────────────────────────────────────────────────────

def compute_component_C(
    ccpp_with_district: gpd.GeoDataFrame,
    ipress_with_district: gpd.GeoDataFrame,
    distritos: gpd.GeoDataFrame,
    mode: str = "baseline",
) -> pd.DataFrame:
    """Compute component C: mean distance (km) to nearest emergency IPRESS.

    Distance is global -- the nearest emergency IPRESS anywhere in Peru,
    not restricted to the same district. This correctly represents access
    for residents of districts with no in-district emergency facility.

    C_raw           = mean Euclidean distance in km (EPSG:32718)
    C_norm_inverted = 1 - min_max(C_raw)  -> smaller distance = higher score

    Not normalised by n_ccpp: mean distance is already a per-district spatial
    average; km/populated-centre has no meaningful interpretation.

    Districts with n_ccpp == 0 have no CCPP points to measure from ->
    C_raw = NaN -> excluded from ranking.

    Returns
    -------
    DataFrame [UBIGEO, mean_dist_km, C_raw, C_norm_inverted]
    """
    flag = flag_tiene_emergencia(ipress_with_district, mode=mode)
    ipress_emerg = ipress_with_district[flag].copy()

    if len(ipress_emerg) == 0:
        raise ValueError(
            f"No emergency-capable IPRESS found for mode={mode!r}. "
            "Cannot compute component C."
        )

    # Global nearest search in EPSG:32718 (metres)
    nearest_df = nearest_ipress_per_ccpp(ccpp_with_district, ipress_emerg)

    # Attach district UBIGEO to each CCPP via index join
    ccpp_dist = ccpp_with_district[["UBIGEO"]].join(
        nearest_df.set_index("ccpp_index")["distance_m"]
    )

    mean_dist = (
        ccpp_dist[ccpp_dist["UBIGEO"].notna()]
        .groupby("UBIGEO")["distance_m"]
        .mean()
        .rename("mean_dist_m")
        .reset_index()
    )
    mean_dist["UBIGEO"] = mean_dist["UBIGEO"].astype(int)

    result = distritos[["UBIGEO"]].copy()
    result = result.merge(mean_dist, on="UBIGEO", how="left")
    result["mean_dist_km"]    = result["mean_dist_m"] / 1_000
    result["C_raw"]           = result["mean_dist_km"]
    result["C_norm_inverted"] = 1.0 - _minmax(result["C_raw"])

    return result[["UBIGEO", "mean_dist_km", "C_raw", "C_norm_inverted"]]


# ─────────────────────────────────────────────────────────────────────────────
# Index builder
# ─────────────────────────────────────────────────────────────────────────────

def build_index(
    A: pd.DataFrame,
    B: pd.DataFrame,
    C: pd.DataFrame,
    weights: tuple = (1 / 3, 1 / 3, 1 / 3),
) -> pd.DataFrame:
    """Combine the three normalised components into a composite access index.

    index = wA * A_norm + wB * B_norm + wC * C_norm_inverted   range [0, 1]
    Higher index -> better emergency healthcare access.

    Districts where any component is NaN receive index = NaN and rank = NaN.
    NaN districts are included in the output but excluded from the ranking.

    Parameters
    ----------
    A, B, C : DataFrames from compute_component_{A,B,C}.
    weights  : (wA, wB, wC) tuple, should sum to 1.

    Returns
    -------
    DataFrame with all raw and normalised columns from A, B, C plus
    'index' (float [0,1]) and 'rank' (Int64, 1 = best access).
    """
    wA, wB, wC = weights

    result = (
        A.merge(B, on="UBIGEO", how="outer")
         .merge(C, on="UBIGEO", how="outer")
    )

    result["index"] = (
        wA * result["A_norm"]
        + wB * result["B_norm"]
        + wC * result["C_norm_inverted"]
    )

    result["rank"] = (
        result["index"]
        .rank(ascending=False, method="min", na_option="keep")
        .where(result["index"].notna())
        .astype("Int64")
    )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Specification comparison
# ─────────────────────────────────────────────────────────────────────────────

def compare_specifications(
    baseline_df: pd.DataFrame,
    alternative_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge baseline and alternative index DataFrames for comparison.

    Columns identical across both specs (n_ccpp, total_atenciones, B_raw,
    B_norm) appear once. Columns that differ per spec (n_ipress_emergencia,
    A_raw, A_norm, mean_dist_km, C_raw, C_norm_inverted, index, rank) are
    suffixed '_baseline' and '_alt'.

    Adds rank_change_abs = |rank_baseline - rank_alt|, NaN where either
    rank is missing. Raw columns (n_ipress_emergencia, total_atenciones,
    mean_dist_km, n_ccpp) are retained so readers can inspect the inputs
    behind each district's position.

    Returns
    -------
    DataFrame with one row per district, all components, and rank comparison.
    """
    shared = {"UBIGEO", "n_ccpp", "total_atenciones", "B_raw", "B_norm"}
    differ = [c for c in baseline_df.columns if c not in shared]

    b = baseline_df.rename(columns={c: f"{c}_baseline" for c in differ})
    a = alternative_df.rename(columns={c: f"{c}_alt"      for c in differ})

    alt_cols = [f"{c}_alt" for c in differ if f"{c}_alt" in a.columns]
    result = b.merge(a[["UBIGEO"] + alt_cols], on="UBIGEO", how="outer")

    # Int64 -> float for NaN-safe subtraction, then back to Int64
    rb = result["rank_baseline"].astype(float)
    ra = result["rank_alt"].astype(float)
    result["rank_change_abs"] = (rb - ra).abs().round().astype("Int64")

    return result
