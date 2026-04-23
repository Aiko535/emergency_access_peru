"""Orchestrator: load → clean → save all four datasets to data/processed/.

Run from the project root:
    python run_cleaning.py
"""

import time

from src.data_loader import load_distritos, load_ipress, load_emergencias, load_ccpp
from src.cleaning import clean_distritos, clean_ipress, clean_emergencias, clean_ccpp
from src.utils import ensure_dir

PROCESSED = "data/processed"


def main() -> None:
    ensure_dir(PROCESSED)
    t0 = time.time()
    summary: list[tuple[str, int, int, str]] = []

    # ── DISTRITOS ────────────────────────────────────────────────────────────
    print("Loading distritos ...", end=" ", flush=True)
    gdf_dist_raw = load_distritos()
    gdf_dist = clean_distritos(gdf_dist_raw)
    gdf_dist.to_file(f"{PROCESSED}/distritos.gpkg", driver="GPKG")
    print("done")
    summary.append(("DISTRITOS", len(gdf_dist_raw), len(gdf_dist), "distritos.gpkg"))

    valid_ubigeos = set(gdf_dist["UBIGEO"])

    # ── IPRESS ───────────────────────────────────────────────────────────────
    print("Loading IPRESS ...", end=" ", flush=True)
    df_ipress_raw = load_ipress()
    df_ipress_all, gdf_ipress_geo = clean_ipress(df_ipress_raw)
    df_ipress_all.to_parquet(f"{PROCESSED}/ipress_clean.parquet", index=False)
    gdf_ipress_geo.to_file(f"{PROCESSED}/ipress_geo.gpkg", driver="GPKG")
    print("done")
    summary.append(("IPRESS (all rows)",   len(df_ipress_raw), len(df_ipress_all),  "ipress_clean.parquet"))
    summary.append(("IPRESS (geo subset)", len(df_ipress_raw), len(gdf_ipress_geo), "ipress_geo.gpkg"))

    # ── EMERGENCIAS ──────────────────────────────────────────────────────────
    print("Loading emergencias ...", end=" ", flush=True)
    df_emerg_raw = load_emergencias()
    df_emerg = clean_emergencias(df_emerg_raw, valid_ubigeos=valid_ubigeos)
    df_emerg.to_parquet(f"{PROCESSED}/emergencias_clean.parquet", index=False)
    print("done")
    summary.append(("EMERGENCIAS", len(df_emerg_raw), len(df_emerg), "emergencias_clean.parquet"))

    # ── CENTROS POBLADOS ─────────────────────────────────────────────────────
    print("Loading centros poblados ...", end=" ", flush=True)
    gdf_ccpp_raw = load_ccpp()
    gdf_ccpp = clean_ccpp(gdf_ccpp_raw)
    gdf_ccpp.to_file(f"{PROCESSED}/centros_poblados.gpkg", driver="GPKG")
    print("done")
    summary.append(("CENTROS POBLADOS", len(gdf_ccpp_raw), len(gdf_ccpp), "centros_poblados.gpkg"))

    # ── Summary table ─────────────────────────────────────────────────────────
    print()
    print(f"  {'Dataset':<24} {'Raw':>9}   {'Clean':>9}   {'Retained':>9}   Output")
    print("  " + "-" * 75)
    for label, before, after, output in summary:
        pct = after / before * 100 if before else 0.0
        print(f"  {label:<24} {before:>9,}   {after:>9,}   {pct:>8.1f}%   {output}")
    print()
    print(f"  All outputs saved to {PROCESSED}/   ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
