"""
RC Validation Script
====================
Reads capacity_addition_analysis.csv from a previous run, picks one or more
technologies whose rc_capex_equivalent_input_units you want to test, and finds
the exact breakeven factor via adaptive binary search.

Mode A — ADAPTIVE (default):
    Starts at factor=1.0, then probes in the right direction, then bisects.
    After N_ITERATIONS total runs the breakeven factor is pinned to a bracket
    of width  initial_step / 2^(N_ITERATIONS-2).

Mode B — FIXED (legacy):
    Runs every factor in SENSITIVITY_FACTORS. Set ADAPTIVE = False to use this.

Usage
-----
Edit the CONFIG section below, then run the script.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from zen_garden import run

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG — edit these values
# ═══════════════════════════════════════════════════════════════════════════════

# Folder that contains a previous run (must have capacity_addition_analysis.csv)
PREVIOUS_RUN_FOLDER = r"outputs_20260430-101235\standard"

# Dataset to re-run (same one used in the previous run)
DATASET = "5_multiple_time_steps_per_year"

# Technologies to adjust.  Use None to interactively pick from the CSV.
# Example: ["photovoltaics_copy"]  or  None  for interactive selection
TECHNOLOGIES = ["photovoltaics_copy"]

# ── Mode A: Adaptive binary search ──────────────────────────────────────────
ADAPTIVE = True

# Total number of model runs in adaptive mode.
# Run 1: probe factor=1.0
# Run 2: probe 0.9 or 1.1 depending on result → establishes bracket
# Runs 3–N: binary search within bracket
# After N runs the bracket width = INITIAL_STEP / 2^(N-2)
# e.g. N=5, step=0.1 → bracket ±0.0125  (~1.25% of RC)
N_ITERATIONS = 5

# Size of the first step away from 1.0 when establishing the bracket
INITIAL_STEP = 0.1   # i.e. first probes are 0.9 and/or 1.1

# A technology is considered "built" when total capacity addition exceeds this
BUILT_THRESHOLD_GW = 1e-4

# ── Mode B: Fixed sensitivity factors (ADAPTIVE = False) ────────────────────
SENSITIVITY_FACTORS = [0.90, 0.95, 1.00, 1.05, 1.10]

# Base config to use (solver settings etc.)
BASE_CONFIG = "./config.json"

# ═══════════════════════════════════════════════════════════════════════════════


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_rc_analysis(run_folder: str, dataset: str) -> pd.DataFrame:
    """Load capacity_addition_analysis.csv — accepts path with or without dataset subfolder."""
    base = Path(run_folder)
    direct      = base / "capacity_addition_analysis.csv"
    with_dataset = base / dataset / "capacity_addition_analysis.csv"

    if direct.exists():
        csv_path = direct
    elif with_dataset.exists():
        csv_path = with_dataset
    else:
        raise FileNotFoundError(
            f"Could not find capacity_addition_analysis.csv. Tried:\n"
            f"  {direct}\n  {with_dataset}\n"
            "Make sure PREVIOUS_RUN_FOLDER points to the correct run folder."
        )

    df = pd.read_csv(csv_path, index_col=list(range(4)))
    df.index.names = ["technology", "capacity_type", "node", "year"]
    print(f"Loaded RC analysis from: {csv_path}")
    return df


def select_technologies(df: pd.DataFrame) -> list[str]:
    """Interactively let the user pick which technologies to test."""
    rc_col = "rc_capex_equivalent_input_units"
    if rc_col not in df.columns:
        raise ValueError(
            f"Column '{rc_col}' not found in CSV. "
            "Make sure you ran the model with the updated postprocess.py."
        )
    candidates = (
        df[rc_col].dropna().reset_index()
        .groupby("technology")[rc_col].mean()
        .sort_values(ascending=False)
    )
    candidates = candidates[candidates.abs() > 1e-6]

    print("\nAvailable technologies with non-zero rc_capex_equivalent_input_units:")
    print("-" * 60)
    for i, (tech, val) in enumerate(candidates.items()):
        print(f"  [{i}]  {tech:35s}  RC = {val:+.2f} Euro/kW")
    print("-" * 60)
    print("Enter comma-separated indices (e.g. 0,2) or press Enter for ALL:")
    raw = input("> ").strip()
    if raw == "":
        return list(candidates.index)
    indices = [int(x.strip()) for x in raw.split(",")]
    return [list(candidates.index)[i] for i in indices]


def get_rc_per_tech(
    df: pd.DataFrame, technologies: list[str]
) -> dict[str, dict]:
    """
    Return RC info per technology, broken down by node and year.

    For each tech returns:
      - "per_node_year":  {(node, year): rc}  — full resolution
      - "per_node_y0":    {node: rc}           — first year per node (used for patching)
      - "nodes":          list of nodes present
      - "first_year":     the first investment year in the data
    """
    rc_col = "rc_capex_equivalent_input_units"
    result = {}
    for tech in technologies:
        vals = df.xs(tech, level="technology")[rc_col].dropna()
        if vals.empty:
            print(f"  WARNING: no RC data for {tech}, skipping.")
            continue

        rc_df = vals.reset_index()  # columns: capacity_type, node, year, rc_col
        first_year = int(rc_df["year"].min())
        nodes = sorted(rc_df["node"].unique())

        # Full (node, year) table
        per_node_year = (
            rc_df.groupby(["node", "year"])[rc_col].mean().to_dict()
        )

        # Per-node RC for the first investment year only
        per_node_y0 = {
            node: float(
                rc_df[rc_df["year"] == first_year]
                .groupby("node")[rc_col].mean()
                .get(node, rc_df[rc_col].mean())
            )
            for node in nodes
        }

        result[tech] = {
            "per_node_year": per_node_year,
            "per_node_y0":   per_node_y0,
            "nodes":         nodes,
            "first_year":    first_year,
        }

        print(f"  {tech}  (using year {first_year} RC per node for patching):")
        max_len = max(len(n) for n in nodes)
        for node in nodes:
            y0_rc = per_node_y0[node]
            print(f"    {node:{max_len}s}  year {first_year}: RC = {y0_rc:+.2f} Euro/kW  ← patch target")
            for (n, y), rc in sorted(per_node_year.items()):
                if n == node and y != first_year:
                    print(f"    {' '*max_len}  year {y}:   RC = {rc:+.2f} Euro/kW")

    return result


def patch_dataset(
    dataset: str,
    rc_per_tech: dict[str, dict],
    factor: float,
) -> str:
    """
    Copy dataset to a temp dir and write a node-specific
    capex_specific_conversion.csv for each technology, reducing each node's
    capex by  factor * RC_node_year0.

    Why per-node CSV instead of a single default_value?
      The breakeven capex differs per node because the operational shadow prices
      (how much the grid values capacity) differ per node.  A uniform reduction
      would simultaneously over-reduce some nodes and under-reduce others,
      making the binary search converge to a meaningless average.

    Why year-0 RC?
      The model invests primarily in the first available year.  Later years have
      a shorter remaining depreciation window, so their RC is higher — they are
      harder to make competitive.  Using year-0 ensures the search finds the
      factor at which the technology first becomes buildable anywhere.
    """
    src = Path(dataset).resolve()
    tmp_dir = Path(tempfile.mkdtemp(prefix="zen_rc_val_"))
    dst = tmp_dir / src.name
    shutil.copytree(src, dst)

    for tech, rc_info in rc_per_tech.items():
        attr_path = (
            dst / "set_technologies" / "set_conversion_technologies" / tech / "attributes.json"
        )
        if not attr_path.exists():
            print(f"  WARNING: attributes.json not found for {tech}, skipping.")
            continue
        with open(attr_path) as f:
            attrs = json.load(f)
        if "capex_specific_conversion" not in attrs:
            print(f"  WARNING: capex_specific_conversion not in {tech}/attributes.json.")
            continue

        original = attrs["capex_specific_conversion"]["default_value"]
        unit     = attrs["capex_specific_conversion"].get("unit", "Euro/kW")

        # Build per-node capex values
        rows = []
        for node, rc_node in rc_info["per_node_y0"].items():
            new_val = original - factor * rc_node
            rows.append({"node": node, "capex_specific_conversion": round(new_val, 6)})
            print(
                f"    {tech} / {node}: {original:.2f} → {new_val:.2f} {unit}  "
                f"(Δ = {-factor*rc_node:+.2f}, RC_y0 = {rc_node:.2f})"
            )

        # Write CSV — ZEN-garden reads this and overrides default_value per node
        csv_path = attr_path.parent / "capex_specific_conversion.csv"
        pd.DataFrame(rows).to_csv(csv_path, index=False)

    return str(dst)


def run_one(
    factor: float,
    dataset: str,
    rc_per_tech: dict[str, float],
    base_output: str,
    base_config: str,
    technologies: list[str],
    iteration: int,
) -> tuple[float, pd.DataFrame]:
    """Patch dataset, run model, return (total_capacity_addition, detail_df)."""
    label = f"iter_{iteration:02d}_factor_{factor:.4f}"
    print(f"\n{'='*62}")
    print(f"  Iteration {iteration}  |  factor = {factor:.4f}  |  {label}")
    print(f"{'='*62}")

    patched = patch_dataset(dataset, rc_per_tech, factor)
    dataset_name = Path(patched).name
    result_folder = os.path.abspath(os.path.join(base_output, label))

    # build config
    os.makedirs(result_folder, exist_ok=True)
    with open(base_config) as f:
        config = json.load(f)
    config.pop("plugins", None)
    config["solver"]["solver_options"]["LogFile"] = os.path.join(result_folder, "solver.log")
    tmp_cfg = os.path.join(result_folder, "config_tmp.json")
    with open(tmp_cfg, "w") as f:
        json.dump(config, f, indent=4)

    run(
        config=tmp_cfg,
        dataset=os.path.abspath(patched),
        folder_output=result_folder,
    )

    # read back
    csv_path = Path(result_folder) / dataset_name / "capacity_addition_analysis.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path, index_col=list(range(4)))
        df.index.names = ["technology", "capacity_type", "node", "year"]
        mask = df.index.get_level_values("technology").isin(technologies)
        df_tech = df[mask][["value"]].copy()
    else:
        df_tech = pd.DataFrame()

    total_cap = float(df_tech["value"].sum()) if not df_tech.empty else 0.0
    built = total_cap > BUILT_THRESHOLD_GW
    print(f"  → total capacity addition = {total_cap:.6f} GW  |  built = {built}")

    # Per-node, per-year breakdown so we can see WHICH node/year flips first
    if not df_tech.empty:
        detail = (
            df_tech.reset_index()
            .groupby(["technology", "node", "year"])["value"]
            .sum()
        )
        print("  Per-node / per-year capacity addition:")
        for (tech, node, yr), cap in detail.items():
            flag = " ← BUILT" if cap > BUILT_THRESHOLD_GW else ""
            print(f"    {tech}  {node}  year {yr}: {cap:.6f} GW{flag}")

    # cleanup temp dataset
    shutil.rmtree(Path(patched).parent, ignore_errors=True)

    return total_cap, df_tech


# ── Adaptive search ──────────────────────────────────────────────────────────

def adaptive_search(
    dataset: str,
    rc_per_tech: dict[str, float],
    base_output: str,
    base_config: str,
    technologies: list[str],
    n_iter: int,
    initial_step: float,
) -> list[dict]:
    """
    Binary search for the breakeven factor.

    Iteration 1 : probe factor = 1.0
    Iteration 2 : probe 1.0 - step (if built at 1.0) or 1.0 + step (if not)
                  → establishes bracket [lo, hi] with lo=unbuilt, hi=built
    Iterations 3–n : bisect the bracket
    """
    history = []
    iteration = 0

    def probe(factor):
        nonlocal iteration
        iteration += 1
        total_cap, df_detail = run_one(
            factor, dataset, rc_per_tech, base_output,
            base_config, technologies, iteration,
        )
        built = total_cap > BUILT_THRESHOLD_GW
        history.append({
            "iteration": iteration,
            "factor": factor,
            "total_capacity_GW": total_cap,
            "built": built,
        })
        return built, total_cap

    # ── Iteration 1: anchor at 1.0 ───────────────────────────────────────────
    built_at_1, _ = probe(1.0)

    if built_at_1:
        # RC overestimates → true breakeven is below 1.0
        # Iteration 2: try 1.0 - step
        built_at_low, _ = probe(1.0 - initial_step)
        if built_at_low:
            lo, hi = 1.0 - 2 * initial_step, 1.0 - initial_step
            print(f"\n  Both 1.0 and {1.0-initial_step:.2f} built → bracket set to [{lo:.4f}, {hi:.4f}]")
        else:
            lo, hi = 1.0 - initial_step, 1.0
    else:
        # RC underestimates → true breakeven is above 1.0
        # Iteration 2: try 1.0 + step
        built_at_high, _ = probe(1.0 + initial_step)
        if not built_at_high:
            lo, hi = 1.0 + initial_step, 1.0 + 2 * initial_step
            print(f"\n  Neither 1.0 nor {1.0+initial_step:.2f} built → bracket set to [{lo:.4f}, {hi:.4f}]")
        else:
            lo, hi = 1.0, 1.0 + initial_step

    print(f"\n  Bracket after 2 iterations: [{lo:.4f}, {hi:.4f}]")

    # ── Iterations 3–n: binary search ────────────────────────────────────────
    remaining = n_iter - 2
    for i in range(remaining):
        mid = (lo + hi) / 2.0
        built_mid, _ = probe(mid)
        if built_mid:
            hi = mid
        else:
            lo = mid
        print(f"  Bracket: [{lo:.4f}, {hi:.4f}]  (width = {hi-lo:.4f})")

    mid_f = (lo + hi) / 2
    print(f"\n  ✓ Final bracket: [{lo:.4f}, {hi:.4f}]")
    print(f"    True breakeven factor ≈ {mid_f:.4f}  (±{(hi-lo)/2:.4f})")
    for tech, rc_info in rc_per_tech.items():
        print(f"    {tech}  (per-node breakeven capex reductions):")
        for node, rc_y0 in rc_info["per_node_y0"].items():
            estimated  = rc_y0
            true_rc    = mid_f * rc_y0
            print(
                f"      {node}: estimated RC = {estimated:.1f} Euro/kW  |  "
                f"true RC ≈ {true_rc:.1f} Euro/kW  |  "
                f"factor correction = {mid_f:.4f}"
            )

    return history


# ── Fixed sensitivity run ─────────────────────────────────────────────────────

def fixed_sensitivity(
    dataset: str,
    rc_per_tech: dict[str, float],
    base_output: str,
    base_config: str,
    technologies: list[str],
    factors: list[float],
) -> list[dict]:
    """Run every factor in the fixed list."""
    history = []
    for i, factor in enumerate(factors, start=1):
        total_cap, _ = run_one(
            factor, dataset, rc_per_tech, base_output,
            base_config, technologies, i,
        )
        history.append({
            "iteration": i,
            "factor": factor,
            "total_capacity_GW": total_cap,
            "built": total_cap > BUILT_THRESHOLD_GW,
        })
    return history


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # Load previous RC analysis
    print(f"\nLoading RC analysis from: {PREVIOUS_RUN_FOLDER}")
    df_rc = load_rc_analysis(PREVIOUS_RUN_FOLDER, DATASET)

    # Select technologies
    technologies = TECHNOLOGIES if TECHNOLOGIES is not None else select_technologies(df_rc)
    print(f"\nSelected technologies: {technologies}")

    # Get RC values
    print("\nRC values (Euro/kW):")
    rc_per_tech = get_rc_per_tech(df_rc, technologies)
    if not rc_per_tech:
        print("No valid RC values found. Exiting.")
        return

    # Output folder
    now = datetime.now()
    time_str = now.strftime("%Y%m%d-%H%M%S")
    base_output = f"./outputs_{time_str}/rc_validation"

    # Run
    if ADAPTIVE:
        print(f"\nMode: ADAPTIVE binary search  ({N_ITERATIONS} iterations, step={INITIAL_STEP})")
        history = adaptive_search(
            DATASET, rc_per_tech, base_output, BASE_CONFIG,
            technologies, N_ITERATIONS, INITIAL_STEP,
        )
    else:
        print(f"\nMode: FIXED sensitivity  factors={SENSITIVITY_FACTORS}")
        history = fixed_sensitivity(
            DATASET, rc_per_tech, base_output, BASE_CONFIG,
            technologies, SENSITIVITY_FACTORS,
        )

    # Summary table
    df_hist = pd.DataFrame(history).sort_values("factor")
    print("\n" + "=" * 62)
    print("RUN HISTORY (sorted by factor)")
    print("=" * 62)
    print(df_hist.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # Save
    os.makedirs(base_output, exist_ok=True)
    summary_csv = os.path.join(base_output, "validation_summary.csv")
    df_hist.to_csv(summary_csv, index=False)
    print(f"\nSummary saved to: {summary_csv}")


if __name__ == "__main__":
    main()
