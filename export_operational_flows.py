"""
Export operational flows (production and consumption by technology and carrier)
from a ZEN-garden result folder.

Outputs (in <output_folder>/operational_flows/):
  flow_conversion_output.csv   – production by tech × carrier × node × timestep
  flow_conversion_input.csv    – consumption by tech × carrier × node × timestep
  flow_import.csv              – carrier imports by node × timestep
  flow_export.csv              – carrier exports by node × timestep
  annual_summary.csv           – annual energy totals (TWh) per tech/carrier/node/year
  carrier_balance.csv          – full carrier balance per node × carrier × year (TWh)
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# ── allow running from repo root without installing the package ──────────────
sys.path.insert(0, str(Path(__file__).parent))
from zen_garden.postprocess.results import Results


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def hours_per_ts(r: Results) -> float:
    """Return duration of each operational timestep in hours."""
    sc = next(iter(r.solution_loader.scenarios.values()))
    n_ts = sc.system.unaggregated_time_steps_per_year
    return 8760.0 / n_ts


def safe_get(r: Results, name: str) -> pd.Series | pd.DataFrame | None:
    """Fetch a component; return None if empty."""
    df = r.get_df(name)
    if df is None or (isinstance(df, (pd.Series, pd.DataFrame)) and df.empty):
        return None
    return df


def to_df(s) -> pd.DataFrame:
    """Convert Series with MultiIndex to DataFrame."""
    if isinstance(s, pd.Series):
        return s.to_frame("value")
    return s


def add_year_column(df: pd.DataFrame, r: Results) -> pd.DataFrame:
    """
    ZEN-garden stores operational timesteps as a flat index 0...(n_ts*n_years - 1).
    Map each timestep to the corresponding optimisation year index (0-based).
    """
    sc = next(iter(r.solution_loader.scenarios.values()))
    n_ts = sc.system.unaggregated_time_steps_per_year
    # find the time dimension in the index
    time_level = None
    for lvl in df.index.names:
        if "time" in lvl.lower():
            time_level = lvl
            break
    if time_level is None:
        return df
    df = df.copy()
    df["year_index"] = df.index.get_level_values(time_level) // n_ts
    ref = sc.system.reference_year
    df["year"] = ref + df["year_index"]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main export
# ─────────────────────────────────────────────────────────────────────────────

def export_flows(result_path: str, output_dir: str | None = None):
    print(f"\n{'='*60}")
    print(f"Loading results from: {result_path}")
    r = Results(result_path)
    sc = next(iter(r.solution_loader.scenarios.values()))

    h = hours_per_ts(r)
    n_ts = sc.system.unaggregated_time_steps_per_year
    ref_year = sc.system.reference_year
    n_years = sc.system.optimized_years
    print(f"  Timesteps/year: {n_ts}  |  Hours/timestep: {h:.4f}")
    print(f"  Years: {ref_year} – {ref_year + n_years - 1}")

    # Output directory
    if output_dir is None:
        output_dir = os.path.join(result_path, "operational_flows")
    os.makedirs(output_dir, exist_ok=True)
    print(f"  Writing to: {output_dir}\n")

    # ── 1. Raw operational flows ──────────────────────────────────────────────
    raw_exports = {
        "flow_conversion_output": "Production by technology & carrier [GW]",
        "flow_conversion_input":  "Consumption by technology & carrier [GW]",
        "flow_import":            "Carrier imports [GW]",
        "flow_export":            "Carrier exports [GW]",
        "flow_transport":         "Transport flows [GW]",
        "flow_storage_charge":    "Storage charge [GW]",
        "flow_storage_discharge": "Storage discharge [GW]",
    }

    raw_dfs = {}
    for var, desc in raw_exports.items():
        data = safe_get(r, var)
        if data is None:
            print(f"  [skip] {var} – empty")
            continue
        df = to_df(data)
        df = add_year_column(df, r)
        out_path = os.path.join(output_dir, f"{var}.csv")
        df.to_csv(out_path)
        raw_dfs[var] = df
        print(f"  [ok] {var:<35} -> {os.path.basename(out_path)}  ({len(df):,} rows)")

    # ── 2. Annual energy summary (TWh) ───────────────────────────────────────
    print("\nBuilding annual summary (TWh)...")
    annual_rows = []

    for var in ["flow_conversion_output", "flow_conversion_input",
                "flow_import", "flow_export"]:
        if var not in raw_dfs:
            continue
        df = raw_dfs[var].copy()
        # energy = flow [GW] × duration [h] → GWh → /1000 → TWh
        df["energy_twh"] = df["value"] * h / 1000.0

        # group by everything except the time-operation index → sum per year
        group_cols = [c for c in df.index.names
                      if "time" not in c.lower()] + ["year"]
        df_reset = df.reset_index()
        grp = df_reset.groupby(group_cols)["energy_twh"].sum().reset_index()
        grp["variable"] = var
        annual_rows.append(grp)

    if annual_rows:
        annual = pd.concat(annual_rows, ignore_index=True)
        annual_path = os.path.join(output_dir, "annual_summary.csv")
        annual.to_csv(annual_path, index=False)
        print(f"  [ok] annual_summary.csv  ({len(annual):,} rows)")
    else:
        annual = pd.DataFrame()

    # ── 3. Carrier balance per node × year ───────────────────────────────────
    print("\nBuilding carrier balance (TWh)...")
    balance_rows = []

    # production
    if "flow_conversion_output" in raw_dfs:
        df = raw_dfs["flow_conversion_output"].reset_index()
        df["energy_twh"] = df["value"] * h / 1000.0
        # index names typically: set_technologies, set_carriers, set_nodes, time_operation
        tech_col  = next((c for c in df.columns if "technolog" in c.lower()), None)
        carr_col  = next((c for c in df.columns if "carrier" in c.lower()), None)
        node_col  = next((c for c in df.columns if "node" in c.lower()), None)
        for _, grp in df.groupby([tech_col, carr_col, node_col, "year"]):
            row = grp.iloc[0]
            balance_rows.append({
                "carrier":    row[carr_col],
                "node":       row[node_col],
                "year":       row["year"],
                "technology": row[tech_col],
                "direction":  "production",
                "energy_twh": grp["energy_twh"].sum(),
            })

    # consumption
    if "flow_conversion_input" in raw_dfs:
        df = raw_dfs["flow_conversion_input"].reset_index()
        df["energy_twh"] = df["value"] * h / 1000.0
        tech_col  = next((c for c in df.columns if "technolog" in c.lower()), None)
        carr_col  = next((c for c in df.columns if "carrier" in c.lower()), None)
        node_col  = next((c for c in df.columns if "node" in c.lower()), None)
        for _, grp in df.groupby([tech_col, carr_col, node_col, "year"]):
            row = grp.iloc[0]
            balance_rows.append({
                "carrier":    row[carr_col],
                "node":       row[node_col],
                "year":       row["year"],
                "technology": row[tech_col],
                "direction":  "consumption",
                "energy_twh": grp["energy_twh"].sum(),
            })

    # imports / exports
    for var, direction in [("flow_import", "import"), ("flow_export", "export")]:
        if var not in raw_dfs:
            continue
        df = raw_dfs[var].reset_index()
        df["energy_twh"] = df["value"] * h / 1000.0
        carr_col = next((c for c in df.columns if "carrier" in c.lower()), None)
        node_col = next((c for c in df.columns if "node" in c.lower()), None)
        for _, grp in df.groupby([carr_col, node_col, "year"]):
            row = grp.iloc[0]
            balance_rows.append({
                "carrier":    row[carr_col],
                "node":       row[node_col],
                "year":       row["year"],
                "technology": f"[{direction}]",
                "direction":  direction,
                "energy_twh": grp["energy_twh"].sum(),
            })

    if balance_rows:
        balance = pd.DataFrame(balance_rows)
        balance_path = os.path.join(output_dir, "carrier_balance.csv")
        balance.to_csv(balance_path, index=False)
        print(f"  [ok] carrier_balance.csv  ({len(balance):,} rows)")

        # ── Pretty-print a summary for electricity ────────────────────────────
        print("\n" + "="*60)
        print("ELECTRICITY BALANCE SUMMARY (TWh/year, year 0 = first opt. year)")
        print("="*60)
        for carrier in sorted(balance["carrier"].unique()):
            sub = balance[balance["carrier"] == carrier]
            print(f"\n  Carrier: {carrier.upper()}")
            pivot = sub.pivot_table(
                index=["node", "technology", "direction"],
                columns="year",
                values="energy_twh",
                aggfunc="sum",
            ).round(2)
            print(pivot.to_string())

    print(f"\nDone. All files written to: {output_dir}\n")
    return output_dir


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export operational flows from a ZEN-garden result folder."
    )
    parser.add_argument(
        "result_path",
        nargs="?",
        default=r"C:\Users\felix\Documents\GitHub\ZEN-garden\outputs_20260528-175237\rc_analysis\6_cb_rc_model",
        help="Path to the result folder (containing var_dict.h5 etc.)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory (default: <result_path>/operational_flows/)",
    )
    args = parser.parse_args()
    export_flows(args.result_path, args.out)
