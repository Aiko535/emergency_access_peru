"""Orchestrator: static visualizations for the access index (Task 4).

Loads all processed index outputs, calls the six plot functions in
src/visualization.py, and saves PNG files to output/figures/ at dpi=200.

Run from the project root:
    python run_visualization.py
"""

import time

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from src.utils import ensure_dir
from src.visualization import (
    plot_index_distribution,
    plot_top_bottom_districts,
    plot_distance_by_department,
    plot_supply_vs_activity,
    plot_rank_changes,
    plot_component_heatmap,
)

PROCESSED = "data/processed"
FIGURES   = "output/figures"
DPI       = 200


def _banner(text: str) -> None:
    print(f"\n{'-' * 60}\n  {text}\n{'-' * 60}", flush=True)


def _save(fig: plt.Figure, filename: str) -> None:
    path = f"{FIGURES}/{filename}"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved  {path}", flush=True)


def main() -> None:
    ensure_dir(FIGURES)
    t0 = time.time()

    # ── Load data ─────────────────────────────────────────────────────────────
    _banner("Loading data")

    distritos  = gpd.read_file(f"{PROCESSED}/distritos.gpkg")
    print(f"  distritos.gpkg          ({len(distritos):,} districts)")

    baseline   = pd.read_parquet(f"{PROCESSED}/district_index_baseline.parquet")
    print(f"  district_index_baseline ({len(baseline):,} rows)")

    alternative = pd.read_parquet(f"{PROCESSED}/district_index_alternative.parquet")
    print(f"  district_index_alternative ({len(alternative):,} rows)")

    comparison  = pd.read_parquet(f"{PROCESSED}/district_index_comparison.parquet")
    print(f"  district_index_comparison  ({len(comparison):,} rows)")

    # ── Figures ───────────────────────────────────────────────────────────────
    _banner("Generating figures")

    print("  [1/6] Distribucion del indice (KDE overlay) ...")
    fig = plot_index_distribution(comparison)
    _save(fig, "fig01_index_distribution.png")

    print("  [2/6] Top 15 / Bottom 15 distritos (barplot) ...")
    fig = plot_top_bottom_districts(baseline, distritos, n=15)
    _save(fig, "fig02_top_bottom_districts.png")

    print("  [3/6] Distancia por departamento (boxplot) ...")
    fig = plot_distance_by_department(baseline, distritos)
    _save(fig, "fig03_distance_by_department.png")

    print("  [4/6] Oferta vs actividad (scatter) ...")
    fig = plot_supply_vs_activity(baseline)
    _save(fig, "fig04_supply_vs_activity.png")

    print("  [5/6] Cambio de rango (scatter diagonal) ...")
    fig = plot_rank_changes(comparison)
    _save(fig, "fig05_rank_changes.png")

    print("  [6/6] Heatmap de componentes (top/changers/bottom) ...")
    fig = plot_component_heatmap(baseline, comparison, distritos, n=30)
    _save(fig, "fig06_component_heatmap.png")

    # ── Summary ───────────────────────────────────────────────────────────────
    _banner("Done")
    print(f"  6 figures saved to {FIGURES}/  (dpi={DPI})")
    print(f"  Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
