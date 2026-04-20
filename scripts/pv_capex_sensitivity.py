"""Run technology parameter sensitivity and plot capacity_addition RC/value.

The script modifies one technology input parameter (for conversion or transport
technologies), runs ZEN-garden for each factor, extracts capacity_addition
value/reduced_cost for selected locations (or edges), restores original inputs,
and writes both CSV and PNG outputs.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Technology sensitivity runner with plots"
    )
    parser.add_argument(
        "--dataset",
        default="12_multiple_in_output_carriers_conversion_edit",
        help="Dataset folder name",
    )
    parser.add_argument(
        "--technology",
        default="photovoltaics",
        help="Technology folder name",
    )
    parser.add_argument(
        "--technology-type",
        choices=["conversion", "transport"],
        default="conversion",
        help="Technology class folder",
    )
    parser.add_argument(
        "--parameter-key",
        default="capex_specific_conversion",
        help="Parameter key in attributes.json to perturb",
    )
    parser.add_argument(
        "--factors",
        default="1.0,0.9,0.8,0.7,0.6,0.5",
        help="Comma-separated multipliers for parameter-key",
    )
    parser.add_argument(
        "--locations",
        default="CH",
        help="Comma-separated set_location values to track (for transport use edges like CH-DE)",
    )
    parser.add_argument("--year", type=int, default=1, help="Target yearly step")
    parser.add_argument(
        "--capacity-type", default="power", help="Target capacity type"
    )
    parser.add_argument(
        "--run-command",
        default="zen-garden",
        help="Command used to run ZEN-garden",
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Optional output filename prefix",
    )
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="Optional persistent directory for sensitivity outputs",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, content: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(content, handle, indent=2)
        handle.write("\n")


def _extract_metric_row(
    output_folder: Path,
    technology: str,
    location: str,
    year: int,
    capacity_type: str,
) -> tuple[float | None, float | None]:
    capacity_csv = output_folder / "capacity_addition_analysis.csv"
    if not capacity_csv.exists():
        return None, None

    df = pd.read_csv(capacity_csv)
    mask = (
        (df["set_technologies"] == technology)
        & (df["set_capacity_types"] == capacity_type)
        & (df["set_location"] == location)
        & (pd.to_numeric(df["set_time_steps_yearly"], errors="coerce") == year)
    )
    subset = df.loc[mask]
    if subset.empty:
        return None, None
    row = subset.iloc[0]
    return float(row["value"]), float(row["reduced_cost"])


def _plot_results(df: pd.DataFrame, output_png: Path, title: str) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    for location in sorted(df["location"].dropna().unique()):
        subset = df[df["location"] == location].sort_values("factor")
        ax1.plot(
            subset["factor"],
            subset["capacity_addition_value"],
            marker="o",
            label=location,
        )
        ax2.plot(
            subset["factor"],
            subset["capacity_addition_reduced_cost"],
            marker="o",
            label=location,
        )

    ax1.set_ylabel("capacity_addition value")
    ax1.grid(True, alpha=0.3)
    ax1.legend(title="location/edge")

    ax2.set_xlabel("parameter factor")
    ax2.set_ylabel("reduced_cost")
    ax2.grid(True, alpha=0.3)
    ax2.legend(title="location/edge")

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output_png, dpi=160)
    plt.close(fig)


def run() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    dataset_folder = repo_root / args.dataset
    output_folder = repo_root / "outputs" / args.dataset
    if args.artifact_dir is not None:
        artifact_dir = Path(args.artifact_dir)
        if not artifact_dir.is_absolute():
            artifact_dir = (repo_root / artifact_dir).resolve()
    else:
        artifact_dir = (repo_root / "outputs" / "sensitivity_artifacts" / args.dataset)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    location_list = [item.strip() for item in args.locations.split(",") if item.strip()]
    if not location_list:
        raise ValueError("Please provide at least one location/edge in --locations")

    if args.technology_type == "conversion":
        subfolder = "set_conversion_technologies"
    else:
        subfolder = "set_transport_technologies"

    attr_path = (
        dataset_folder
        / "set_technologies"
        / subfolder
        / args.technology
        / "attributes.json"
    )
    if not attr_path.exists():
        raise FileNotFoundError(f"Could not find attributes file: {attr_path}")

    factors = [float(item.strip()) for item in args.factors.split(",") if item.strip()]

    original = _read_json(attr_path)
    param_entry = original.get(args.parameter_key, {})
    if "default_value" not in param_entry:
        raise KeyError(
            f"{args.parameter_key}.default_value not found in {attr_path}"
        )

    base_value = float(param_entry["default_value"])
    print(f"Base {args.technology} {args.parameter_key} = {base_value}")

    results = []
    try:
        for factor in factors:
            modified = _read_json(attr_path)
            modified[args.parameter_key]["default_value"] = base_value * factor
            _write_json(attr_path, modified)

            cmd = shlex.split(args.run_command) + [f"--dataset={args.dataset}"]
            print(f"\nRunning: {' '.join(cmd)} with capex factor {factor}")
            try:
                completed = subprocess.run(
                    cmd,
                    cwd=repo_root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError:
                cmd = [sys.executable, "-m", "zen_garden", f"--dataset={args.dataset}"]
                print(f"Fallback run: {' '.join(cmd)}")
                completed = subprocess.run(
                    cmd,
                    cwd=repo_root,
                    check=False,
                    capture_output=True,
                    text=True,
                )

            for location in location_list:
                value = None
                reduced_cost = None
                if completed.returncode == 0:
                    value, reduced_cost = _extract_metric_row(
                        output_folder=output_folder,
                        technology=args.technology,
                        location=location,
                        year=args.year,
                        capacity_type=args.capacity_type,
                    )

                results.append(
                    {
                        "technology": args.technology,
                        "parameter_key": args.parameter_key,
                        "location": location,
                        "year": args.year,
                        "capacity_type": args.capacity_type,
                        "factor": factor,
                        "parameter_value": base_value * factor,
                        "return_code": completed.returncode,
                        "capacity_addition_value": value,
                        "capacity_addition_reduced_cost": reduced_cost,
                    }
                )

            if completed.returncode != 0:
                print("Run failed. Last 40 stderr lines:")
                stderr_lines = completed.stderr.splitlines()
                for line in stderr_lines[-40:]:
                    print(line)
    finally:
        _write_json(attr_path, original)
        print("\nRestored original attributes.json")

    result_df = pd.DataFrame(results)
    prefix = args.output_prefix or f"{args.technology}_{args.parameter_key}_sensitivity"
    out_csv = artifact_dir / f"{prefix}.csv"
    out_png = artifact_dir / f"{prefix}.png"
    result_df.to_csv(out_csv, index=False)
    print(f"Saved sensitivity summary to: {out_csv}")
    _plot_results(
        result_df,
        output_png=out_png,
        title=(
            f"{args.technology}: {args.parameter_key} sensitivity "
            f"(year={args.year}, capacity={args.capacity_type})"
        ),
    )
    print(f"Saved sensitivity plot to: {out_png}")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    run()
