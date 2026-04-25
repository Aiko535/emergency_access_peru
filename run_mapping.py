"""Orquestador de mapas — ejecutar desde la raíz del proyecto.

Uso (PowerShell):
    python run_mapping.py

Salidas en output/figures/:
    map01_choropleth_national.png
    map02_choropleth_comparison.png
    map03_lima_ipress.png
    map04_interactive_national.html
    map05_interactive_comparison.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from mapping import (
    folium_comparison_interactive,
    folium_national_interactive,
    plot_choropleth_comparison,
    plot_choropleth_national,
    plot_lima_with_ipress,
)
from metrics import flag_tiene_emergencia

# ── Rutas ─────────────────────────────────────────────────────────────────────
DATA_DIR   = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "output" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DISTRITOS_GPKG     = DATA_DIR / "distritos.gpkg"
IPRESS_GPKG        = DATA_DIR / "ipress_with_district.gpkg"
INDEX_BASELINE     = DATA_DIR / "district_index_baseline.parquet"
COMPARISON_PARQUET = DATA_DIR / "district_index_comparison.parquet"


def load_data():
    print("Cargando datos...")

    distritos = gpd.read_file(DISTRITOS_GPKG)
    ipress    = gpd.read_file(IPRESS_GPKG)
    index_df  = pd.read_parquet(INDEX_BASELINE)
    comp_df   = pd.read_parquet(COMPARISON_PARQUET)

    flag = flag_tiene_emergencia(ipress, mode="baseline")
    ipress_emerg = ipress[flag].copy()
    print(f"  IPRESS de emergencia (baseline flag): {len(ipress_emerg):,} / {len(ipress):,} total")

    return distritos, ipress_emerg, index_df, comp_df


def main():
    distritos, ipress_emerg, index_df, comp_df = load_data()

    print("Generando map01_choropleth_national.png ...")
    fig = plot_choropleth_national(distritos, index_df, column="index")
    fig.savefig(OUTPUT_DIR / "map01_choropleth_national.png", dpi=150, bbox_inches="tight")
    plt_close(fig)
    print("  Guardado.")

    print("Generando map02_choropleth_comparison.png ...")
    fig = plot_choropleth_comparison(distritos, comp_df)
    fig.savefig(OUTPUT_DIR / "map02_choropleth_comparison.png", dpi=150, bbox_inches="tight")
    plt_close(fig)
    print("  Guardado.")

    print("Generando map03_lima_ipress.png ...")
    fig = plot_lima_with_ipress(distritos, ipress_emerg, index_df)
    fig.savefig(OUTPUT_DIR / "map03_lima_ipress.png", dpi=150, bbox_inches="tight")
    plt_close(fig)
    print("  Guardado.")

    print("Generando map04_interactive_national.html ...")
    m = folium_national_interactive(distritos, index_df, ipress_emerg)
    m.save(str(OUTPUT_DIR / "map04_interactive_national.html"))
    print("  Guardado.")

    print("Generando map05_interactive_comparison.html ...")
    m = folium_comparison_interactive(distritos, comp_df)
    m.save(str(OUTPUT_DIR / "map05_interactive_comparison.html"))
    print("  Guardado.")

    print("\nOK - Todos los mapas generados en:", OUTPUT_DIR)


def plt_close(fig):
    import matplotlib.pyplot as plt
    plt.close(fig)


if __name__ == "__main__":
    main()