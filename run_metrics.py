"""Orchestrator: district-level access index (Task 3).

Loads all processed outputs from Tasks 1 and 2, computes both index
specifications (baseline and alternative), compares them, and saves
results to data/processed/ and output/tables/.

Run from the project root:
    python run_metrics.py
"""

import time

import pandas as pd
import geopandas as gpd

from src.metrics import (
    compute_component_A,
    compute_component_B,
    compute_component_C,
    build_index,
    compare_specifications,
)
from src.utils import ensure_dir

PROCESSED = "data/processed"
TABLES    = "output/tables"

WEIGHTS_BASELINE    = (1 / 3, 1 / 3, 1 / 3)
WEIGHTS_ALTERNATIVE = (0.25, 0.25, 0.50)


def _banner(text: str) -> None:
    print(f"\n{'-' * 60}\n  {text}\n{'-' * 60}", flush=True)


def _step(text: str) -> None:
    print(f"  {text} ...", end=" ", flush=True)


def _done(extra: str = "") -> None:
    msg = f"done  {extra}" if extra else "done"
    print(msg, flush=True)


def _print_top_bottom(df: pd.DataFrame, label: str, n: int = 10) -> None:
    """Print top-n and bottom-n ranked districts from an index DataFrame."""
    ranked = df[df["rank"].notna()].sort_values("rank")
    top    = ranked.head(n)
    bottom = ranked.tail(n)

    print(f"\n  --- Top {n} districts ({label}) ---")
    print(f"  {'Rank':>4}  {'UBIGEO':>8}  {'Index':>7}  {'A_norm':>7}  {'B_norm':>7}  {'C_norm_inv':>10}")
    for _, row in top.iterrows():
        print(
            f"  {int(row['rank']):>4}  {row['UBIGEO']:>8}  "
            f"{row['index']:>7.4f}  {row['A_norm']:>7.4f}  "
            f"{row['B_norm']:>7.4f}  {row['C_norm_inverted']:>10.4f}"
        )

    print(f"\n  --- Bottom {n} districts ({label}) ---")
    print(f"  {'Rank':>4}  {'UBIGEO':>8}  {'Index':>7}  {'A_norm':>7}  {'B_norm':>7}  {'C_norm_inv':>10}")
    for _, row in bottom.iterrows():
        print(
            f"  {int(row['rank']):>4}  {row['UBIGEO']:>8}  "
            f"{row['index']:>7.4f}  {row['A_norm']:>7.4f}  "
            f"{row['B_norm']:>7.4f}  {row['C_norm_inverted']:>10.4f}"
        )


def _print_rank_changes(comparison: pd.DataFrame, n: int = 20) -> None:
    """Print districts with the largest absolute rank change."""
    changed = (
        comparison[comparison["rank_change_abs"].notna()]
        .sort_values("rank_change_abs", ascending=False)
        .head(n)
    )
    print(f"\n  --- Top {n} districts by rank change (baseline vs alternative) ---")
    print(
        f"  {'UBIGEO':>8}  {'rank_base':>9}  {'rank_alt':>8}  "
        f"{'change':>6}  {'index_base':>10}  {'index_alt':>9}"
    )
    for _, row in changed.iterrows():
        rb = int(row["rank_baseline"]) if pd.notna(row["rank_baseline"]) else "NaN"
        ra = int(row["rank_alt"])      if pd.notna(row["rank_alt"])      else "NaN"
        ch = int(row["rank_change_abs"])
        print(
            f"  {row['UBIGEO']:>8}  {rb!s:>9}  {ra!s:>8}  "
            f"{ch:>6}  {row['index_baseline']:>10.4f}  {row['index_alt']:>9.4f}"
        )


def _save_top_bottom_csv(df: pd.DataFrame, label: str, n: int = 10) -> None:
    """Save top-n and bottom-n ranked districts to a single CSV file."""
    ranked = df[df["rank"].notna()].sort_values("rank")
    top    = ranked.head(n).copy()
    bottom = ranked.tail(n).copy()
    top["group"]    = "top"
    bottom["group"] = "bottom"
    out = pd.concat([top, bottom], ignore_index=True)
    path = f"{TABLES}/top_bottom_{n}_districts_{label}.csv"
    out.to_csv(path, index=False)
    print(f"    {path}")


def main() -> None:
    ensure_dir(PROCESSED)
    ensure_dir(TABLES)
    t0 = time.time()

    # ── Load all processed outputs ────────────────────────────────────────────
    _banner("Loading processed outputs")

    _step("distritos.gpkg")
    distritos = gpd.read_file(f"{PROCESSED}/distritos.gpkg")
    _done(f"({len(distritos):,} districts)")

    _step("ipress_with_district.gpkg")
    ipress_with_dist = gpd.read_file(f"{PROCESSED}/ipress_with_district.gpkg")
    _done(f"({len(ipress_with_dist):,} IPRESS)")

    _step("ccpp_with_district.gpkg")
    ccpp_with_dist = gpd.read_file(f"{PROCESSED}/ccpp_with_district.gpkg")
    _done(f"({len(ccpp_with_dist):,} CCPP)")

    _step("emergencias_clean.parquet")
    emergencias = pd.read_parquet(f"{PROCESSED}/emergencias_clean.parquet")
    _done(f"({len(emergencias):,} rows)")

    _step("district_spatial_summary.gpkg")
    district_summary = gpd.read_file(f"{PROCESSED}/district_spatial_summary.gpkg")
    _done(f"({len(district_summary):,} districts)")

    # n_ccpp is the population proxy for components A and B
    n_ccpp = district_summary.set_index("UBIGEO")["n_ccpp"]

    # ── Baseline specification ────────────────────────────────────────────────
    _banner("Baseline specification  (weights=1/3,1/3,1/3  mode='baseline')")

    _step("component A -- facility availability")
    A_base = compute_component_A(ipress_with_dist, distritos, n_ccpp, mode="baseline")
    n_emer_base = (A_base["n_ipress_emergencia"] > 0).sum()
    _done(f"({n_emer_base:,} districts with >=1 emergency IPRESS)")

    _step("component B -- emergency activity")
    B_base = compute_component_B(emergencias, distritos, n_ccpp)
    _done(f"(total attentions {B_base['total_atenciones'].sum():,.0f})")

    _step("component C -- spatial access  [this runs sjoin_nearest]")
    C_base = compute_component_C(ccpp_with_dist, ipress_with_dist, distritos, mode="baseline")
    med_km = C_base["mean_dist_km"].median()
    _done(f"(median district mean dist {med_km:.1f} km)")

    _step("building baseline index")
    baseline = build_index(A_base, B_base, C_base, weights=WEIGHTS_BASELINE)
    n_ranked = baseline["rank"].notna().sum()
    _done(f"({n_ranked:,} districts ranked)")

    _step("saving district_index_baseline.parquet")
    baseline.to_parquet(f"{PROCESSED}/district_index_baseline.parquet", index=False)
    _done()

    # ── Alternative specification ─────────────────────────────────────────────
    _banner("Alternative specification  (weights=0.25,0.25,0.50  mode='alternative')")

    _step("component A -- facility availability")
    A_alt = compute_component_A(ipress_with_dist, distritos, n_ccpp, mode="alternative")
    n_emer_alt = (A_alt["n_ipress_emergencia"] > 0).sum()
    _done(f"({n_emer_alt:,} districts with >=1 emergency IPRESS)")

    _step("component B -- emergency activity  [shared with baseline]")
    B_alt = B_base.copy()   # B does not depend on flag mode
    _done("(reused)")

    _step("component C -- spatial access  [this runs sjoin_nearest]")
    C_alt = compute_component_C(ccpp_with_dist, ipress_with_dist, distritos, mode="alternative")
    med_km_alt = C_alt["mean_dist_km"].median()
    _done(f"(median district mean dist {med_km_alt:.1f} km)")

    _step("building alternative index")
    alternative = build_index(A_alt, B_alt, C_alt, weights=WEIGHTS_ALTERNATIVE)
    n_ranked_alt = alternative["rank"].notna().sum()
    _done(f"({n_ranked_alt:,} districts ranked)")

    _step("saving district_index_alternative.parquet")
    alternative.to_parquet(f"{PROCESSED}/district_index_alternative.parquet", index=False)
    _done()

    # ── Specification comparison ──────────────────────────────────────────────
    _banner("Comparing specifications")

    _step("merging baseline and alternative")
    comparison = compare_specifications(baseline, alternative)
    n_changed = (comparison["rank_change_abs"] > 0).sum()
    max_change = comparison["rank_change_abs"].max()
    _done(f"({n_changed:,} districts changed rank, max change {max_change})")

    _step("saving district_index_comparison.parquet")
    comparison.to_parquet(f"{PROCESSED}/district_index_comparison.parquet", index=False)
    _done()

    # ── CSV tables ────────────────────────────────────────────────────────────
    _banner("Saving output tables")
    print(f"  Output directory: {TABLES}/")

    _save_top_bottom_csv(baseline,    "baseline",    n=10)
    _save_top_bottom_csv(alternative, "alternative", n=10)

    # Top-20 rank changers
    changed_sorted = (
        comparison[comparison["rank_change_abs"].notna()]
        .sort_values("rank_change_abs", ascending=False)
        .head(20)
    )
    changed_path = f"{TABLES}/rank_changes_top20.csv"
    changed_sorted.to_csv(changed_path, index=False)
    print(f"    {changed_path}")

    # ── Console summaries ─────────────────────────────────────────────────────
    _print_top_bottom(baseline,    "baseline",    n=10)
    _print_top_bottom(alternative, "alternative", n=10)
    _print_rank_changes(comparison, n=20)

    # ── Overall stats ─────────────────────────────────────────────────────────
    _banner("Summary statistics")

    print(f"  Districts total                        {len(distritos):>8,}")
    print(f"  Districts ranked (baseline)            {n_ranked:>8,}")
    print(f"  Districts ranked (alternative)         {n_ranked_alt:>8,}")
    print(f"  Districts excluded (n_ccpp=0)          {(n_ccpp == 0).sum():>8,}")
    print()
    print(f"  Emergency IPRESS (baseline)            {n_emer_base:>8,}  districts")
    print(f"  Emergency IPRESS (alternative)         {n_emer_alt:>8,}  districts")
    print()
    print(f"  Rank changes vs alternative            {n_changed:>8,}  districts")
    print(f"  Largest absolute rank change           {max_change!s:>8}")
    print()
    idx_b = baseline["index"].dropna()
    print(f"  Baseline index  mean={idx_b.mean():.3f}  "
          f"std={idx_b.std():.3f}  "
          f"min={idx_b.min():.3f}  "
          f"max={idx_b.max():.3f}")
    idx_a = alternative["index"].dropna()
    print(f"  Alternative     mean={idx_a.mean():.3f}  "
          f"std={idx_a.std():.3f}  "
          f"min={idx_a.min():.3f}  "
          f"max={idx_a.max():.3f}")
    print()
    print(f"  Outputs saved:")
    print(f"    {PROCESSED}/district_index_baseline.parquet")
    print(f"    {PROCESSED}/district_index_alternative.parquet")
    print(f"    {PROCESSED}/district_index_comparison.parquet")
    print(f"    {TABLES}/top_bottom_10_districts_baseline.csv")
    print(f"    {TABLES}/top_bottom_10_districts_alternative.csv")
    print(f"    {TABLES}/rank_changes_top20.csv")
    print()
    print(f"  Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
