"""Cleaning functions — one per dataset, pure transformations."""

import pandas as pd
import pandas.api.types as pat
import geopandas as gpd

# ── Peru bounding box (teacher convention: NORTE = longitude, ESTE = latitude)
_NORTE_MIN, _NORTE_MAX = -81.5, -68.5  # longitude range
_ESTE_MIN,  _ESTE_MAX  = -18.5,  0.5   # latitude range

_CRS_WGS84 = "EPSG:4326"


# ─────────────────────────────────────────────────────────────────────────────
# Districts
# ─────────────────────────────────────────────────────────────────────────────

def clean_distritos(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Standardize the districts GeoDataFrame.

    - Renames IDDIST to UBIGEO and casts it to int (master join key).
    - Ensures CRS is EPSG:4326.

    Returns 1,873 rows expected.
    """
    gdf = gdf.copy()
    gdf = gdf.rename(columns={"IDDIST": "UBIGEO"})
    gdf["UBIGEO"] = gdf["UBIGEO"].astype(str).astype(int)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.set_crs(_CRS_WGS84)
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# IPRESS
# ─────────────────────────────────────────────────────────────────────────────

def clean_ipress(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Clean the IPRESS health-facilities catalogue.

    Returns
    -------
    df_all : pd.DataFrame
        All facilities after deduplication by Código Único (~20,793 rows).
    gdf_geo : gpd.GeoDataFrame
        Facilities with valid coordinates as Point geometry, CRS EPSG:4326
        (~7,953 rows).

    Cleaning steps
    --------------
    - Drop duplicate rows by Código Único, keeping the first occurrence.
    - For gdf_geo: discard rows where NORTE or ESTE is null or zero, then
      apply the Peru bounding-box filter
      (NORTE ∈ [-81.5, -68.5]; ESTE ∈ [-18.5, 0.5]).
    - Build geometry with gpd.points_from_xy(NORTE, ESTE) following the
      teacher convention (NORTE = longitude, ESTE = latitude).
    """
    # "Código Único" is always column index 1 regardless of how the accented
    # name is decoded by the platform's active encoding.
    codigo_col = df.columns[1]

    # ── Deduplicate ──────────────────────────────────────────────────────────
    df_all = df.drop_duplicates(subset=[codigo_col], keep="first").copy()

    # ── Build geo subset ─────────────────────────────────────────────────────
    mask = (
        df_all["NORTE"].notna()
        & df_all["ESTE"].notna()
        & (df_all["NORTE"] != 0)
        & (df_all["ESTE"] != 0)
        & df_all["NORTE"].between(_NORTE_MIN, _NORTE_MAX)
        & df_all["ESTE"].between(_ESTE_MIN, _ESTE_MAX)
    )
    geo_df = df_all[mask].copy()

    gdf_geo = gpd.GeoDataFrame(
        geo_df,
        geometry=gpd.points_from_xy(geo_df["NORTE"], geo_df["ESTE"]),
        crs=_CRS_WGS84,
    )

    return df_all, gdf_geo


# ─────────────────────────────────────────────────────────────────────────────
# Emergencias
# ─────────────────────────────────────────────────────────────────────────────

def clean_emergencias(
    df: pd.DataFrame,
    valid_ubigeos: set | None = None,
) -> pd.DataFrame:
    """Clean the SUSALUD emergency-care production dataset.

    Parameters
    ----------
    df : pd.DataFrame
        Raw emergencias DataFrame as returned by load_emergencias.
    valid_ubigeos : set, optional
        Set of integer UBIGEO codes present in the cleaned districts GeoDataFrame.
        If provided, rows whose UBIGEO is not in this set are dropped (~12 rows).

    Cleaning steps
    --------------
    1. Drop fully duplicated rows (~19,458 exact copies removed).
    2. Convert NRO_TOTAL_ATENCIONES and NRO_TOTAL_ATENDIDOS to numeric;
       NE_0001 placeholders (~13% of rows) become NaN.
    3. Group by (UBIGEO, CO_IPRESS, ANHO, MES, SEXO, EDAD) and sum numeric
       columns to resolve partial resubmissions. Groups where all values are
       NaN remain NaN (min_count=1).
    4. Cast UBIGEO to int and drop rows not present in valid_ubigeos (if given).

    Returns ~323,295 rows expected.
    """
    df = df.copy()

    # 1. Remove exact duplicates across all columns
    df = df.drop_duplicates()

    # 2. Numeric conversion — NE_0001 and any non-numeric value → NaN
    for col in ("NRO_TOTAL_ATENCIONES", "NRO_TOTAL_ATENDIDOS"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. Group and sum to resolve partial resubmissions
    group_keys = ["UBIGEO", "CO_IPRESS", "ANHO", "MES", "SEXO", "EDAD"]
    text_cols = [
        c for c in ("DEPARTAMENTO", "PROVINCIA", "DISTRITO", "SECTOR", "CATEGORIA", "RAZON_SOC")
        if c in df.columns
    ]

    agg = {c: "first" for c in text_cols}
    # min_count=1 keeps NaN when the entire group is NaN (no valid reports)
    agg["NRO_TOTAL_ATENCIONES"] = lambda x: x.sum(min_count=1)
    agg["NRO_TOTAL_ATENDIDOS"]  = lambda x: x.sum(min_count=1)

    df = df.groupby(group_keys, as_index=False).agg(agg)

    # 4. Cast UBIGEO to int and filter to known districts
    df["UBIGEO"] = df["UBIGEO"].astype(int)
    if valid_ubigeos is not None:
        df = df[df["UBIGEO"].isin(valid_ubigeos)].copy()

    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Centros Poblados
# ─────────────────────────────────────────────────────────────────────────────

def clean_ccpp(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clean the IGN populated-centers GeoDataFrame.

    Cleaning steps
    --------------
    - Keep only INEI-sourced records (FUENTE normalised to uppercase == 'INEI'),
      which includes the minor 'inei' variant (~1,145 rows). Yields 75,164 rows.
    - Exclude records with 9-digit CÓDIGO (IGN-internal codes, not valid UBIGEO).
    - Derive UBIGEO as the first 6 characters of CÓDIGO, cast to nullable Int64.
      Records with null CÓDIGO (~38,862) retain UBIGEO = NaN; their district
      assignment is deferred to a spatial join in the analysis phase.
    - Retain only UBIGEO, NOM_POBLAD, and geometry.
    - Ensure CRS is EPSG:4326.

    Returns ~74,767 rows expected (75,164 INEI minus ~397 with 9-digit CÓDIGO).

    Note: the Y attribute column has a known data bug (Y=X in ~45% of rows).
    Only the geometry column is used for spatial operations.
    """
    gdf = gdf.copy()

    # Locate the CÓDIGO column — its name may contain a Unicode replacement
    # character (U+FFFD) depending on platform encoding. Identify it by
    # content: the only object column whose values are 9–10 digit strings.
    codigo_col = next(
        c for c in gdf.columns
        if c != "geometry"
        and pat.is_string_dtype(gdf[c])
        and gdf[c].str.match(r"^\d{9,10}$", na=False).any()
    )

    # ── Keep INEI only (case-insensitive) ────────────────────────────────────
    gdf = gdf[gdf["FUENTE"].str.upper() == "INEI"].copy()

    # ── Drop 9-digit codes (IGN-internal, not UBIGEO-compatible) ─────────────
    # Keep rows where CÓDIGO is 10 digits OR null. Null rows have valid geometry
    # and will be assigned a district via spatial join in the analysis phase.
    mask_keep = (gdf[codigo_col].str.len() == 10) | gdf[codigo_col].isna()
    gdf = gdf[mask_keep].copy()

    # ── Derive UBIGEO from first 6 digits of CÓDIGO (NaN where CÓDIGO is null)
    gdf["UBIGEO"] = gdf[codigo_col].str[:6].astype(float).astype("Int64")

    # ── Select output columns ─────────────────────────────────────────────────
    gdf = gdf[["UBIGEO", "NOM_POBLAD", "geometry"]].copy()

    # ── Ensure CRS ────────────────────────────────────────────────────────────
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.set_crs(_CRS_WGS84)

    return gdf.reset_index(drop=True)
