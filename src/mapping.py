"""Cartographic outputs for the emergency healthcare access index.

Static maps  (GeoPandas + matplotlib) -> PNG in output/figures/
Interactive  (Folium)                 -> HTML in output/figures/

Each public function is pure: accepts GeoDataFrames/DataFrames, returns
a Figure or folium.Map. No file I/O — run_mapping.py handles that.

CRS convention: EPSG:4326 for all outputs (matplotlib and Folium).
"""

from __future__ import annotations

import warnings
from typing import Optional

import geopandas as gpd
import mapclassify
import matplotlib.cm as mcm
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import folium
    from folium.plugins import MarkerCluster
    _FOLIUM_OK = True
except ImportError:
    _FOLIUM_OK = False

# ── Shared style constants ────────────────────────────────────────────────────
_CMAP_SEQUENTIAL   = "YlOrRd"
_CMAP_DIVERGING    = "RdBu_r"
_EXCL_COLOR        = "#d9d9d9"
_EXCL_HATCH        = "////"
_EXCL_ALPHA        = 0.5
_BORDER_COLOR      = "white"
_BORDER_WIDTH      = 0.3
_IPRESS_COLOR      = "#1a6faf"
_IPRESS_MARKER     = "o"
_IPRESS_SIZE       = 8
_TOP_CHANGER_COLOR = "#e31a1c"
_TOP_CHANGER_SIZE  = 10
_FOLIUM_TILE       = "CartoDB positron"
_FIG_DPI           = 150


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


def _classify(series: pd.Series, k: int = 5, scheme: str = "quantiles"):
    valid = series.dropna().values
    if scheme == "naturalbreaks":
        return mapclassify.NaturalBreaks(valid, k=k)
    return mapclassify.Quantiles(valid, k=k)


def _excluded_patch() -> mpatches.Patch:
    return mpatches.Patch(
        facecolor=_EXCL_COLOR, hatch=_EXCL_HATCH, alpha=_EXCL_ALPHA,
        label="Sin datos"
    )


def _draw_excluded(ax: plt.Axes, excluded: gpd.GeoDataFrame) -> None:
    if excluded.empty:
        return
    excluded.plot(
        ax=ax,
        color=_EXCL_COLOR,
        hatch=_EXCL_HATCH,
        alpha=_EXCL_ALPHA,
        edgecolor=_BORDER_COLOR,
        linewidth=_BORDER_WIDTH,
    )


def _base_fig(title: str, figsize=(12, 10)):
    fig, ax = plt.subplots(figsize=figsize, dpi=_FIG_DPI)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_axis_off()
    return fig, ax


def _merge_index(gdf, index_df, column):
    gdf = gdf.copy()
    gdf["UBIGEO"] = gdf["UBIGEO"].astype(int)
    idx = index_df.copy()
    idx["UBIGEO"] = idx["UBIGEO"].astype(int)
    merged = gdf.merge(idx, on="UBIGEO", how="left")
    included = merged[merged[column].notna()].copy()
    excluded = merged[merged[column].isna()].copy()
    return included, excluded


def _folium_bins(series: pd.Series, scheme) -> list:
    """Build Folium-compatible bin list: [min, ...mapclassify bins]."""
    return [float(series.min())] + [float(b) for b in scheme.bins]


# ── Public API ────────────────────────────────────────────────────────────────

def plot_choropleth_national(
    distritos: gpd.GeoDataFrame,
    index_df: pd.DataFrame,
    column: str = "index",
) -> plt.Figure:
    distritos = _to_wgs84(distritos.copy())
    included, excluded = _merge_index(distritos, index_df, column)

    scheme = _classify(included[column], k=5, scheme="quantiles")
    bins   = np.concatenate([[included[column].min()], scheme.bins])
    norm   = mcolors.BoundaryNorm(bins, ncolors=256)
    cmap   = plt.get_cmap(_CMAP_SEQUENTIAL)

    fig, ax = _base_fig("Índice de acceso a emergencias — Nacional (baseline, quintiles)")

    included.plot(
        column=column, ax=ax, cmap=cmap, norm=norm,
        edgecolor=_BORDER_COLOR, linewidth=_BORDER_WIDTH,
    )
    _draw_excluded(ax, excluded)

    sm = mcm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.02, ticks=scheme.bins)
    cbar.set_label("Índice de acceso a emergencias (baseline, quintiles)", fontsize=9)
    cbar.ax.set_yticklabels([f"{b:.3f}" for b in scheme.bins], fontsize=7)

    handles = [_excluded_patch()]
    ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.8)
    fig.tight_layout()
    return fig


def plot_choropleth_comparison(
    distritos: gpd.GeoDataFrame,
    comparison_df: pd.DataFrame,
) -> plt.Figure:
    distritos = _to_wgs84(distritos.copy())

    gdf = distritos.copy()
    gdf["UBIGEO"] = gdf["UBIGEO"].astype(int)
    cmp = comparison_df.copy()
    cmp["UBIGEO"] = cmp["UBIGEO"].astype(int)
    merged = gdf.merge(cmp, on="UBIGEO", how="left")

    included_b = merged[merged["index_baseline"].notna()].copy()
    included_a = merged[merged["index_alt"].notna()].copy()
    excluded   = merged[merged["index_baseline"].isna() & merged["index_alt"].isna()].copy()

    vmin = min(included_b["index_baseline"].min(), included_a["index_alt"].min())
    vmax = max(included_b["index_baseline"].max(), included_a["index_alt"].max())
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.get_cmap(_CMAP_SEQUENTIAL)

    fig, axes = plt.subplots(1, 2, figsize=(18, 9), dpi=_FIG_DPI)
    fig.suptitle(
        "Comparación índice: Baseline vs Alternativa",
        fontsize=14, fontweight="bold", y=1.01
    )

    for ax, col, title in zip(
        axes,
        ["index_baseline", "index_alt"],
        ["Baseline", "Alternativa"],
    ):
        ax.set_title(title, fontsize=12, pad=8)
        ax.set_axis_off()
        data = included_b if col == "index_baseline" else included_a
        data.plot(column=col, ax=ax, cmap=cmap, norm=norm,
                  edgecolor=_BORDER_COLOR, linewidth=_BORDER_WIDTH)
        _draw_excluded(ax, excluded)

    sm = mcm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, shrink=0.6, pad=0.02)
    cbar.set_label("Índice de acceso a emergencias", fontsize=9)

    fig.tight_layout()
    return fig


def plot_lima_with_ipress(
    distritos: gpd.GeoDataFrame,
    ipress_emerg: gpd.GeoDataFrame,
    index_df: pd.DataFrame,
) -> plt.Figure:
    distritos = _to_wgs84(distritos.copy())
    ipress    = _to_wgs84(ipress_emerg.copy())

    dept_col = next((c for c in distritos.columns if "departam" in c.lower()), None)
    prov_col = next((c for c in distritos.columns if "provinci" in c.lower()), None)

    if dept_col and prov_col:
        lima = distritos[
            (distritos[dept_col].str.upper() == "LIMA") &
            (distritos[prov_col].str.upper() == "LIMA")
        ].copy()
    else:
        warnings.warn("No DEPARTAMEN/PROVINCIA columns found; showing all districts.")
        lima = distritos.copy()

    lima["UBIGEO"] = lima["UBIGEO"].astype(int)
    idx = index_df.copy()
    idx["UBIGEO"] = idx["UBIGEO"].astype(int)
    lima = lima.merge(idx, on="UBIGEO", how="left")

    included = lima[lima["index"].notna()].copy()
    excluded = lima[lima["index"].isna()].copy()

    lima_bbox = lima.total_bounds
    buf = 0.05
    ipress_clip = ipress.cx[
        lima_bbox[0] - buf : lima_bbox[2] + buf,
        lima_bbox[1] - buf : lima_bbox[3] + buf,
    ].copy()

    scheme = _classify(included["index"], k=5, scheme="quantiles")
    bins   = np.concatenate([[included["index"].min()], scheme.bins])
    norm   = mcolors.BoundaryNorm(bins, ncolors=256)
    cmap   = plt.get_cmap(_CMAP_SEQUENTIAL)

    fig, ax = _base_fig(
        "Lima Metropolitana — Índice de acceso + IPRESS de emergencia",
        figsize=(10, 11),
    )

    included.plot(
        column="index", ax=ax, cmap=cmap, norm=norm,
        edgecolor=_BORDER_COLOR, linewidth=_BORDER_WIDTH,
    )
    _draw_excluded(ax, excluded)

    if not ipress_clip.empty:
        ipress_clip.plot(
            ax=ax, color=_IPRESS_COLOR, marker=_IPRESS_MARKER,
            markersize=_IPRESS_SIZE, alpha=0.75, label="IPRESS con emergencia",
        )

    sm = mcm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.02, ticks=scheme.bins)
    cbar.set_label("Índice de acceso a emergencias (quintiles)", fontsize=9)
    cbar.ax.set_yticklabels([f"{b:.3f}" for b in scheme.bins], fontsize=7)

    handles = [
        mpatches.Patch(color=_IPRESS_COLOR, label="IPRESS con emergencia"),
        _excluded_patch(),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.8)
    fig.tight_layout()
    return fig


def folium_national_interactive(
    distritos: gpd.GeoDataFrame,
    index_df: pd.DataFrame,
    ipress_emerg: gpd.GeoDataFrame,
) -> "folium.Map":
    if not _FOLIUM_OK:
        raise ImportError("folium is not installed. Run: pip install folium")

    distritos = _to_wgs84(distritos.copy())
    ipress    = _to_wgs84(ipress_emerg.copy())

    included, excluded = _merge_index(distritos, index_df, "index")

    for col in ["rank", "index"]:
        if col in included.columns:
            included[col] = included[col].astype(float)
        if col in excluded.columns:
            excluded[col] = excluded[col].astype(float)

    centre = [-9.19, -75.0]  # Peru centroid hardcoded to avoid CRS warning

    m = folium.Map(location=centre, zoom_start=5, tiles=_FOLIUM_TILE)

    scheme = _classify(included["index"], k=5, scheme="quantiles")
    bins   = _folium_bins(included["index"], scheme)

    folium.Choropleth(
        geo_data=included.__geo_interface__,
        data=included[["UBIGEO", "index"]],
        columns=["UBIGEO", "index"],
        key_on="feature.properties.UBIGEO",
        fill_color=_CMAP_SEQUENTIAL,
        fill_opacity=0.75,
        line_opacity=0.2,
        nan_fill_color=_EXCL_COLOR,
        bins=bins,
        legend_name="Índice de acceso a emergencias (quintiles)",
        name="Índice baseline",
    ).add_to(m)

    tooltip_cols = [c for c in ["DISTRITO", "DEPARTAMEN", "index", "rank"] if c in included.columns]
    folium.GeoJson(
        included[tooltip_cols + ["geometry"]],
        style_function=lambda _: {"fillOpacity": 0, "weight": 0},
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_cols,
            aliases=["Distrito", "Departamento", "Índice", "Rank"][:len(tooltip_cols)],
            localize=True,
        ),
        name="Tooltips",
    ).add_to(m)

    if not excluded.empty:
        folium.GeoJson(
            excluded[["geometry"]],
            style_function=lambda _: {
                "fillColor": _EXCL_COLOR, "fillOpacity": 0.5,
                "color": "white", "weight": 0.3,
            },
            name="Sin datos",
        ).add_to(m)

    if not ipress.empty:
        cluster = MarkerCluster(name="IPRESS de emergencia").add_to(m)
        name_col = next(
            (c for c in ipress.columns if "nombre" in c.lower() or "name" in c.lower()), None
        )
        for _, row in ipress.iterrows():
            coords = [row.geometry.y, row.geometry.x]
            popup_text = row[name_col] if name_col else "IPRESS"
            folium.CircleMarker(
                location=coords,
                radius=5,
                color=_IPRESS_COLOR,
                fill=True,
                fill_opacity=0.8,
                popup=folium.Popup(str(popup_text), max_width=200),
            ).add_to(cluster)

    folium.LayerControl().add_to(m)
    return m


def folium_comparison_interactive(
    distritos: gpd.GeoDataFrame,
    comparison_df: pd.DataFrame,
) -> "folium.Map":
    if not _FOLIUM_OK:
        raise ImportError("folium is not installed. Run: pip install folium")

    distritos = _to_wgs84(distritos.copy())

    gdf = distritos.copy()
    gdf["UBIGEO"] = gdf["UBIGEO"].astype(int)
    cmp = comparison_df.copy()
    cmp["UBIGEO"] = cmp["UBIGEO"].astype(int)
    merged = gdf.merge(cmp, on="UBIGEO", how="left")

    included = merged[merged["rank_change_abs"].notna()].copy()
    excluded = merged[merged["rank_change_abs"].isna()].copy()

    for col in ["rank_baseline", "rank_alt", "rank_change_abs", "rank_change"]:
        if col in included.columns:
            included[col] = included[col].astype(float)

    centre = [-9.19, -75.0]

    m = folium.Map(location=centre, zoom_start=5, tiles=_FOLIUM_TILE)

    scheme = _classify(included["rank_change_abs"], k=5, scheme="quantiles")
    bins   = _folium_bins(included["rank_change_abs"], scheme)

    folium.Choropleth(
        geo_data=included.__geo_interface__,
        data=included[["UBIGEO", "rank_change_abs"]],
        columns=["UBIGEO", "rank_change_abs"],
        key_on="feature.properties.UBIGEO",
        fill_color=_CMAP_SEQUENTIAL,
        fill_opacity=0.75,
        line_opacity=0.2,
        nan_fill_color=_EXCL_COLOR,
        bins=bins,
        legend_name="Cambio absoluto en ranking (quintiles)",
        name="Cambio de ranking",
    ).add_to(m)

    tooltip_cols = [
        c for c in ["DISTRITO", "rank_baseline", "rank_alt", "rank_change_abs"]
        if c in included.columns
    ]
    folium.GeoJson(
        included[tooltip_cols + ["geometry"]],
        style_function=lambda _: {"fillOpacity": 0, "weight": 0},
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_cols,
            aliases=["Distrito", "Rank baseline", "Rank alt", "Δ Rank (abs)"][:len(tooltip_cols)],
            localize=True,
        ),
        name="Tooltips",
    ).add_to(m)

    top20 = included.nlargest(20, "rank_change_abs").copy()
    dist_col = next((c for c in top20.columns if "distrito" in c.lower()), None)

    top20_group = folium.FeatureGroup(name="Top 20 cambios de ranking").add_to(m)
    for _, row in top20.iterrows():
        coords = [row.geometry.centroid.y, row.geometry.centroid.x]
        name   = row[dist_col] if dist_col else "Distrito"
        popup_html = (
            f"<b>{name}</b><br>"
            f"Rank baseline: {row.get('rank_baseline', 'N/A'):.0f}<br>"
            f"Rank alt: {row.get('rank_alt', 'N/A'):.0f}<br>"
            f"Δ Rank (abs): {row['rank_change_abs']:.0f}"
        )
        folium.CircleMarker(
            location=coords,
            radius=8,
            color=_TOP_CHANGER_COLOR,
            fill=True,
            fill_color=_TOP_CHANGER_COLOR,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(top20_group)

    if not excluded.empty:
        folium.GeoJson(
            excluded[["geometry"]],
            style_function=lambda _: {
                "fillColor": _EXCL_COLOR, "fillOpacity": 0.5,
                "color": "white", "weight": 0.3,
            },
            name="Sin datos",
        ).add_to(m)

    folium.LayerControl().add_to(m)
    return m