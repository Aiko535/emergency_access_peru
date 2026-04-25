"""Static visualizations for the emergency healthcare access index.

Each public function accepts DataFrames, builds a matplotlib Figure,
and returns it. No side effects, no file I/O — the caller (run_visualization.py)
is responsible for saving.

Palette conventions
-------------------
  Continuous data       : "viridis"
  Two-group categorical : COLOR_TOP (blue) / COLOR_BOTTOM (red)
  Multi-category        : seaborn "Set2"

Axis labels are in Spanish for the final presentation.
"""

import matplotlib
matplotlib.use("Agg")   # non-interactive backend; must precede pyplot import

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# ─────────────────────────────────────────────────────────────────────────────
# Shared style constants
# ─────────────────────────────────────────────────────────────────────────────

COLOR_TOP    = "#2196F3"   # blue   -- best-access districts
COLOR_BOTTOM = "#F44336"   # red    -- worst-access districts
COLOR_CHANGE = "#FF9800"   # orange -- largest rank changers

plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "figure.dpi":        100,
})


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _dept_code(name: str) -> str:
    """Return a 3-letter department abbreviation (upper-case)."""
    return str(name)[:3].upper()


def _district_label(row: pd.Series) -> str:
    """'DISTRITO (DEP)' label for bars and heatmap rows."""
    return f"{row['DISTRITO']} ({_dept_code(row['DEPARTAMEN'])})"


def _merge_names(df: pd.DataFrame, distritos_df: pd.DataFrame) -> pd.DataFrame:
    """Left-join DISTRITO and DEPARTAMEN onto df by UBIGEO (int cast)."""
    names = distritos_df[["UBIGEO", "DISTRITO", "DEPARTAMEN"]].copy()
    names["UBIGEO"] = names["UBIGEO"].astype(int)
    out = df.copy()
    out["UBIGEO"] = out["UBIGEO"].astype(int)
    return out.merge(names, on="UBIGEO", how="left")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Index distribution -- KDE overlay
# ─────────────────────────────────────────────────────────────────────────────

def plot_index_distribution(comparison_df: pd.DataFrame) -> plt.Figure:
    """KDE overlay of the baseline and alternative index distributions.

    Why this chart: shows at a glance that the alternative specification
    shifts and widens the distribution -- more districts reach mid-range
    scores -- without needing to inspect individual district changes.
    A histogram would work but KDE is smoother over 1,800+ observations.

    Answers: Pregunta 4 (sensibilidad metodologica).
    """
    base = comparison_df["index_baseline"].dropna()
    alt  = comparison_df["index_alt"].dropna()

    fig, ax = plt.subplots(figsize=(10, 6))

    sns.kdeplot(base, ax=ax, color=COLOR_TOP,    fill=True, alpha=0.30,
                label="Baseline  (1/3, 1/3, 1/3)")
    sns.kdeplot(alt,  ax=ax, color=COLOR_BOTTOM, fill=True, alpha=0.30,
                label="Alternativa  (0.25, 0.25, 0.50)")

    ax.axvline(base.mean(), color=COLOR_TOP,    linestyle="--", linewidth=1.3,
               label=f"Media baseline = {base.mean():.3f}")
    ax.axvline(alt.mean(),  color=COLOR_BOTTOM, linestyle="--", linewidth=1.3,
               label=f"Media alternativa = {alt.mean():.3f}")

    ax.set_xlabel("Indice de acceso a emergencias  [0 - 1]", fontsize=12)
    ax.set_ylabel("Densidad", fontsize=12)
    ax.set_title(
        "Distribucion del indice de acceso: baseline vs especificacion alternativa\n"
        "(n = 1,812 distritos con al menos un centro poblado asignado)",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=10)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. Top n / Bottom n districts -- horizontal barplot
# ─────────────────────────────────────────────────────────────────────────────

def plot_top_bottom_districts(
    index_df: pd.DataFrame,
    distritos_df: pd.DataFrame,
    n: int = 15,
) -> plt.Figure:
    """Horizontal barplot of the n best and n worst districts (baseline index).

    Why this chart: a ranked bar chart is the most direct answer to
    'which specific districts?'. Horizontal orientation fits long district
    names. Department abbreviation in each label gives geographic context
    without a separate color legend (which would need 15+ colors for 30 bars).

    Answers: Pregunta 3 (que distritos tienen mejor/peor acceso?).
    """
    df = _merge_names(index_df, distritos_df)
    ranked = df[df["rank"].notna()].sort_values("rank")

    top    = ranked.head(n).copy()
    bottom = ranked.tail(n).sort_values("rank", ascending=False).copy()

    top["label"]    = top.apply(_district_label,    axis=1)
    bottom["label"] = bottom.apply(_district_label, axis=1)

    x_max = ranked["index"].max() * 1.12

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharey=False)

    for ax, subset, color, title in [
        (axes[0], top,    COLOR_TOP,    f"Top {n} -- mayor acceso"),
        (axes[1], bottom, COLOR_BOTTOM, f"Bottom {n} -- menor acceso"),
    ]:
        ax.barh(subset["label"], subset["index"], color=color, alpha=0.85)
        ax.set_xlabel("Indice de acceso  (baseline)", fontsize=11)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlim(0, x_max)
        ax.invert_yaxis()   # rank 1 at top

        for patch, val in zip(ax.patches, subset["index"]):
            ax.text(
                val + 0.004,
                patch.get_y() + patch.get_height() / 2,
                f"{val:.3f}",
                va="center", fontsize=8,
            )

    fig.suptitle(
        "Distritos con mayor y menor acceso a atencion de emergencias -- especificacion baseline",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. Distance to nearest emergency IPRESS by department -- boxplot
# ─────────────────────────────────────────────────────────────────────────────

def plot_distance_by_department(
    index_df: pd.DataFrame,
    distritos_df: pd.DataFrame,
) -> plt.Figure:
    """Horizontal boxplot of mean district distance (km) by department.

    Why this chart: a boxplot reveals both central tendency and spread
    within each department -- a bar chart of means would hide the
    within-department heterogeneity that matters for policy. Ordering by
    median makes the national ranking immediately legible.

    Answers: Pregunta 2 (hay brechas geograficas/regionales?).
    """
    df = _merge_names(index_df, distritos_df)
    df = df[df["mean_dist_km"].notna()].copy()

    order = (
        df.groupby("DEPARTAMEN")["mean_dist_km"]
        .median()
        .sort_values(ascending=True)   # ascending so longest distance is at top
        .index.tolist()
    )

    fig, ax = plt.subplots(figsize=(10, 10))
    sns.boxplot(
        data=df,
        x="mean_dist_km",
        y="DEPARTAMEN",
        hue="DEPARTAMEN",
        order=order,
        palette="viridis",
        width=0.55,
        flierprops={"marker": "o", "markersize": 2.5, "alpha": 0.4},
        legend=False,
        ax=ax,
    )

    ax.set_xlabel(
        "Distancia media al IPRESS de emergencia mas cercano (km)", fontsize=11
    )
    ax.set_ylabel("Departamento", fontsize=11)
    ax.set_title(
        "Distancia media al IPRESS de emergencia mas cercano por departamento\n"
        "(un punto por distrito; ordenado por mediana departamental -- especificacion baseline)",
        fontsize=12, fontweight="bold",
    )
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. Supply vs activity scatter (districts with n_ipress_emergencia > 0)
# ─────────────────────────────────────────────────────────────────────────────

def plot_supply_vs_activity(index_df: pd.DataFrame) -> plt.Figure:
    """Scatter: N. emergency IPRESS vs total emergency visits per district.

    Filtered to the 329 districts with >=1 emergency IPRESS (baseline).
    Why filter and not log1p: filtering makes the question more precise --
    'among districts that have emergency supply, does more supply generate
    more activity?' -- and keeps axes in interpretable units for a
    non-technical audience (professor, video presentation).

    Marker size encodes n_ccpp (population proxy).
    Color encodes the composite index (viridis) so outliers can be
    identified as over- or under-performers relative to their peers.

    Answers: Pregunta 1 (la oferta de IPRESS se traduce en mayor actividad?).
    """
    df = index_df[index_df["n_ipress_emergencia"] > 0].copy()
    n  = len(df)

    size_raw = df["n_ccpp"].fillna(1).clip(lower=1)
    s_lo, s_hi = size_raw.min(), size_raw.max()
    if s_lo == s_hi:
        sizes = pd.Series(60.0, index=df.index)
    else:
        sizes = 20 + 280 * (size_raw - s_lo) / (s_hi - s_lo)

    # Y-axis cap: p95 keeps the main cluster legible; outliers drawn as triangles
    p95      = df["total_atenciones"].quantile(0.95)
    y_cap    = p95 * 1.05
    normal   = df[df["total_atenciones"] <= p95]
    outliers = df[df["total_atenciones"] >  p95]

    # Shared color normalisation across all points (vmin/vmax from full df)
    import matplotlib.colors as mcolors
    import matplotlib.cm as mcm
    norm     = mcolors.Normalize(vmin=df["index"].min(), vmax=df["index"].max())
    cmap_obj = mcm.get_cmap("viridis")

    fig, ax = plt.subplots(figsize=(10, 7))

    # Main scatter — normal points
    sc = ax.scatter(
        normal["n_ipress_emergencia"],
        normal["total_atenciones"],
        s=sizes[normal.index],
        c=normal["index"],
        cmap="viridis",
        norm=norm,
        alpha=0.72,
        edgecolors="white",
        linewidths=0.4,
    )
    cbar = fig.colorbar(sc, ax=ax, pad=0.01)
    cbar.set_label("Indice de acceso (baseline)", fontsize=10)

    # Outlier triangles pinned at y = p95 * 1.02
    if len(outliers) > 0:
        y_tri = p95 * 1.02
        for idx, row in outliers.iterrows():
            color = cmap_obj(norm(row["index"]))
            sz    = float(sizes[idx])
            ax.scatter(
                row["n_ipress_emergencia"], y_tri,
                marker="^", s=sz, color=color,
                alpha=0.90, edgecolors="white", linewidths=0.4,
                zorder=5,
            )
            val_k = f"{row['total_atenciones'] / 1_000:.0f}k"
            ax.annotate(
                val_k,
                xy=(row["n_ipress_emergencia"], y_tri),
                xytext=(0, 6), textcoords="offset points",
                ha="center", fontsize=7.5, color="#333333",
            )
        ax.set_ylim(0, y_cap)

    # Size legend
    for rv in [10, 50, 150]:
        if s_lo <= rv <= s_hi:
            sz = 20 + 280 * (rv - s_lo) / (s_hi - s_lo)
            ax.scatter([], [], s=sz, c="gray", alpha=0.6, label=f"{rv} CCPP")
    ax.legend(title="N. centros poblados", fontsize=9, title_fontsize=9,
              loc="upper left")

    cap_note = (
        f"eje Y capeado al p95 ({p95 / 1_000:.0f}k); "
        f"{len(outliers)} outlier(s) como triangulos arriba"
        if len(outliers) > 0 else ""
    )
    ax.set_xlabel(
        "N. de IPRESS con servicios de emergencia en el distrito  (baseline)", fontsize=11
    )
    ax.set_ylabel("Total de atenciones de emergencia registradas", fontsize=11)
    ax.set_title(
        f"Oferta de IPRESS de emergencia vs actividad registrada\n"
        f"(n = {n} distritos con >=1 IPRESS emergencia; tamano = n. centros poblados"
        + (f"; {cap_note})" if cap_note else ")"),
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. Rank-change scatter -- baseline vs alternative
# ─────────────────────────────────────────────────────────────────────────────

def plot_rank_changes(comparison_df: pd.DataFrame) -> plt.Figure:
    """Scatter: rank_baseline (x) vs rank_alt (y) with diagonal reference line.

    Why this chart: directly shows which districts are stable (near the
    diagonal) vs sensitive (far from it). A bar chart of rank differences
    would not reveal whether a district improved or worsened, nor show
    the full joint distribution of both rankings simultaneously.

    Points below the diagonal improved under the alternative spec (more
    weight on spatial access). Top-20 changers are highlighted in orange
    and labelled with their UBIGEO code.

    Answers: Pregunta 4 (robustez de las conclusiones).
    """
    df = comparison_df[
        comparison_df["rank_baseline"].notna() & comparison_df["rank_alt"].notna()
    ].copy()

    top20 = df.nlargest(20, "rank_change_abs")
    rest  = df[~df.index.isin(top20.index)]

    max_rank = int(df[["rank_baseline", "rank_alt"]].max().max())

    fig, ax = plt.subplots(figsize=(8, 8))

    ax.scatter(
        rest["rank_baseline"], rest["rank_alt"],
        s=8, color="lightgray", alpha=0.5, rasterized=True,
        label="Resto de distritos",
    )
    ax.scatter(
        top20["rank_baseline"], top20["rank_alt"],
        s=55, color=COLOR_CHANGE, alpha=0.92, zorder=5,
        label="Top 20 mayor cambio de rango",
    )
    for _, row in top20.iterrows():
        ax.annotate(
            str(int(row["UBIGEO"])),
            xy=(row["rank_baseline"], row["rank_alt"]),
            xytext=(4, 2), textcoords="offset points",
            fontsize=6.0, color="#444444",
        )

    ax.plot([1, max_rank], [1, max_rank], "r--", linewidth=1.0,
            zorder=4, label="Sin cambio (diagonal)")

    ax.set_xlabel("Rango -- especificacion baseline", fontsize=11)
    ax.set_ylabel("Rango -- especificacion alternativa", fontsize=11)
    ax.set_title(
        "Cambio de rango entre especificaciones\n"
        "Puntos bajo la diagonal mejoran con la alternativa (mayor peso en distancia)",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 6. Component heatmap -- top n, top-20 rank changers, bottom n
# ─────────────────────────────────────────────────────────────────────────────

def plot_component_heatmap(
    baseline_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    distritos_df: pd.DataFrame,
    n: int = 30,
) -> plt.Figure:
    """Heatmap of A_norm, B_norm, C_norm_inverted for three district groups.

    Groups (separated by blank rows):
      1. Top n  -- best baseline rank
      2. Top 20 -- largest rank change between specifications
      3. Bottom n -- worst baseline rank

    Why three groups: top/bottom answer Pregunta 3 (which components drive
    position -- availability? activity? distance?). The rank-changer group
    answers Pregunta 4 (what component profile makes a district sensitive
    to weighting?). A scatter or bar chart cannot show simultaneously which
    combination of three components explains each district's position.

    Answers: Pregunta 3 and Pregunta 4.
    """
    df = _merge_names(baseline_df, distritos_df)
    df["label"] = df.apply(_district_label, axis=1)

    ranked = df[df["rank"].notna()].sort_values("rank")
    top_n  = ranked.head(n).copy()
    bot_n  = ranked.tail(n).sort_values("rank", ascending=False).copy()

    top20_ubigeo = (
        comparison_df[comparison_df["rank_change_abs"].notna()]
        .nlargest(20, "rank_change_abs")["UBIGEO"]
        .astype(int)
        .tolist()
    )
    changers = (
        df[df["UBIGEO"].isin(top20_ubigeo)]
        .merge(
            comparison_df[["UBIGEO", "rank_change_abs"]]
            .assign(UBIGEO=lambda d: d["UBIGEO"].astype(int)),
            on="UBIGEO", how="left",
        )
        .sort_values("rank_change_abs", ascending=False)
    )

    COLS   = ["A_norm", "B_norm", "C_norm_inverted"]
    LABELS = ["A: disponibilidad", "B: actividad", "C: acceso espacial"]

    def _block(src: pd.DataFrame, tag: str) -> pd.DataFrame:
        b = src[["label"] + COLS].copy()
        b.insert(0, "grupo", tag)
        return b

    blank = pd.DataFrame([{"grupo": "", "label": "", **{c: np.nan for c in COLS}}])

    combined = pd.concat([
        _block(top_n,    f"Top {n}"),
        blank,
        _block(changers, "Top 20 cambio de rango"),
        blank,
        _block(bot_n,    f"Bottom {n}"),
    ], ignore_index=True)

    heat_data  = combined[COLS].astype(float)
    row_labels = combined["label"].tolist()
    mask       = heat_data.isna()   # blank separator rows show as white

    n_rows     = len(combined)
    fig_height = max(14, n_rows * 0.30)
    fig, ax    = plt.subplots(figsize=(9, fig_height))

    sns.heatmap(
        heat_data,
        ax=ax,
        mask=mask,
        cmap="viridis",
        vmin=0, vmax=1,
        xticklabels=LABELS,
        yticklabels=row_labels,
        linewidths=0.25,
        linecolor="white",
        cbar_kws={
            "label":       "Valor normalizado  [0 - 1]",
            "orientation": "horizontal",
            "shrink":      0.40,
            "pad":         0.03,
        },
    )

    ax.set_xticklabels(LABELS, fontsize=10, rotation=0)
    ax.tick_params(axis="y", labelsize=7.5)

    # Thick white lines to visually separate the three groups
    # top_n: rows 0..n-1 | blank: n | changers: n+1..n+20 | blank: n+21 | bottom: n+22..
    for pos in [n, n + 1, n + 1 + 20, n + 2 + 20]:
        ax.axhline(pos, color="white", linewidth=3)

    # Group labels on the right margin
    group_info = [
        (n / 2,                f"TOP {n}"),
        (n + 1 + 10,           "TOP 20\nCAMBIO"),
        (n + 2 + 20 + n / 2,  f"BOTTOM {n}"),
    ]
    for row_center, glabel in group_info:
        frac_y = 1.0 - (row_center + 0.5) / n_rows
        ax.annotate(
            glabel,
            xy=(1.0, frac_y),
            xycoords="axes fraction",
            xytext=(8, 0),
            textcoords="offset points",
            va="center", ha="left",
            fontsize=8.5, fontweight="bold", color="#333333",
            annotation_clip=False,
        )

    ax.set_title(
        "Perfil de componentes por grupo de distritos  (especificacion baseline)\n"
        f"Grupos: Top {n}  |  Top 20 mayor cambio de rango  |  Bottom {n}",
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout()
    return fig
