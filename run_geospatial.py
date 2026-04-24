"""Orchestrator: spatial joins and district aggregation (Task 2).

Loads the five cleaned outputs from Task 1, runs the geospatial pipeline,
and saves four new outputs to data/processed/.

Run from the project root:
    python run_geospatial.py
"""

import time

import pandas as pd
import geopandas as gpd

from src.geospatial import (
    assign_ipress_to_districts,
    assign_ccpp_to_districts,
    nearest_ipress_per_ccpp,
    aggregate_to_district,
)
from src.utils import ensure_dir

PROCESSED = "data/processed"


def _banner(text: str) -> None:
    print(f"\n{'-' * 60}\n  {text}\n{'-' * 60}", flush=True)


def _step(text: str) -> None:
    print(f"  {text} ...", end=" ", flush=True)


def _done(extra: str = "") -> None:
    msg = f"done  {extra}" if extra else "done"
    print(msg, flush=True)


def main() -> None:
    ensure_dir(PROCESSED)
    t0 = time.time()

    # ── Load Task-1 outputs ───────────────────────────────────────────────────
    _banner("Loading Task-1 outputs")

    _step("distritos.gpkg")
    distritos = gpd.read_file(f"{PROCESSED}/distritos.gpkg")
    _done(f"({len(distritos):,} districts)")

    _step("ipress_geo.gpkg")
    ipress_geo = gpd.read_file(f"{PROCESSED}/ipress_geo.gpkg")
    _done(f"({len(ipress_geo):,} IPRESS with coords)")

    _step("ipress_clean.parquet")
    ipress_all = pd.read_parquet(f"{PROCESSED}/ipress_clean.parquet")
    _done(f"({len(ipress_all):,} IPRESS total)")

    _step("centros_poblados.gpkg")
    ccpp = gpd.read_file(f"{PROCESSED}/centros_poblados.gpkg")
    _done(f"({len(ccpp):,} CCPP, {ccpp['UBIGEO'].isna().sum():,} need district via sjoin)")

    # ── Step 1: Assign IPRESS to districts ───────────────────────────────────
    _banner("Step 1 — Assign IPRESS to districts (point-in-polygon, EPSG:4326)")

    _step("sjoin IPRESS <-> distritos")
    ipress_with_dist = assign_ipress_to_districts(ipress_geo, distritos)
    n_matched   = ipress_with_dist["UBIGEO_district"].notna().sum()
    n_unmatched = ipress_with_dist["UBIGEO_district"].isna().sum()
    _done(f"({n_matched:,} matched, {n_unmatched:,} outside any polygon)")

    _step("saving ipress_with_district.gpkg")
    ipress_with_dist.to_file(f"{PROCESSED}/ipress_with_district.gpkg", driver="GPKG")
    _done()

    # ── Step 2: Assign CCPP to districts ─────────────────────────────────────
    _banner("Step 2 — Assign CCPP to districts (point-in-polygon, EPSG:4326)")

    _step("sjoin CCPP <-> distritos")
    ccpp_with_dist = assign_ccpp_to_districts(ccpp, distritos)
    n_filled     = (ccpp["UBIGEO"].isna() & ccpp_with_dist["UBIGEO"].notna()).sum()
    n_still_nan  = ccpp_with_dist["UBIGEO"].isna().sum()
    n_mismatch_proxy = 0  # actual count emitted as warning by the function
    _done(
        f"({n_filled:,} NaN filled via sjoin, "
        f"{n_still_nan:,} still unassigned)"
    )

    _step("saving ccpp_with_district.gpkg")
    ccpp_with_dist.to_file(f"{PROCESSED}/ccpp_with_district.gpkg", driver="GPKG")
    _done()

    # ── Step 3: Nearest IPRESS per CCPP ──────────────────────────────────────
    _banner("Step 3 — Nearest IPRESS per CCPP (sjoin_nearest, EPSG:32718)")

    _step("computing nearest IPRESS distances")
    nearest_df = nearest_ipress_per_ccpp(ccpp_with_dist, ipress_with_dist)
    med_km = nearest_df["distance_m"].median() / 1_000
    _done(f"(median distance {med_km:.1f} km)")

    # ── Step 4: Aggregate to district ────────────────────────────────────────
    _banner("Step 4 — Aggregate to district level")

    _step("aggregating counts and distances")
    district_summary = aggregate_to_district(
        ipress_geo=ipress_with_dist,
        ipress_all=ipress_all,
        ccpp=ccpp_with_dist,
        distritos=distritos,
        nearest_df=nearest_df,
    )
    _done()

    _step("saving district_spatial_summary.parquet (no geometry)")
    district_summary.drop(columns=["geometry"]).to_parquet(
        f"{PROCESSED}/district_spatial_summary.parquet", index=False
    )
    _done()

    _step("saving district_spatial_summary.gpkg (with geometry)")
    district_summary.to_file(
        f"{PROCESSED}/district_spatial_summary.gpkg", driver="GPKG"
    )
    _done()

    # ── Summary table ─────────────────────────────────────────────────────────
    _banner("Summary")

    ds = district_summary
    print(f"  Districts total                        {len(ds):>8,}")
    print(f"  Districts with >=1 IPRESS (total)       {(ds['n_ipress_total'] > 0).sum():>8,}")
    print(f"  Districts with >=1 IPRESS (geo)         {(ds['n_ipress_geo'] > 0).sum():>8,}")
    print(f"  Districts with >=1 CCPP                 {(ds['n_ccpp'] > 0).sum():>8,}")
    print(f"  Districts with distance data            {ds['mean_dist_nearest_ipress_m'].notna().sum():>8,}")
    print()
    print(f"  IPRESS matched to a district           {n_matched:>8,}  / {len(ipress_geo):,}")
    print(f"  CCPP with district assigned (final)    {ccpp_with_dist['UBIGEO'].notna().sum():>8,}  / {len(ccpp_with_dist):,}")
    print()
    dist_km = district_summary["mean_dist_nearest_ipress_m"].dropna() / 1_000
    print(f"  Mean dist to nearest IPRESS (km)")
    print(f"    median across districts              {dist_km.median():>8.1f}")
    print(f"    p25                                  {dist_km.quantile(0.25):>8.1f}")
    print(f"    p75                                  {dist_km.quantile(0.75):>8.1f}")
    print(f"    max                                  {dist_km.max():>8.1f}")
    print()
    print(f"  Outputs saved to {PROCESSED}/")
    print(f"    ipress_with_district.gpkg")
    print(f"    ccpp_with_district.gpkg")
    print(f"    district_spatial_summary.parquet")
    print(f"    district_spatial_summary.gpkg")
    print()
    print(f"  Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
