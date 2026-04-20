"""Map reduced-cost rows to candidate input parameters.

The script reads
1) objective_coefficients_analysis.csv
2) param_dict.h5
from one output folder and creates a long table that links each selected
variable row (with reduced cost information) to candidate input parameters.

Candidate matching is based on shared index dimensions and exact coordinate
matches in those shared dimensions.

Example:
    python scripts/map_rc_to_input_parameters.py \
        --output-folder outputs/12_multiple_in_output_carriers_conversion_edit \
        --only-nonzero-rc
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


MEASURE_COLUMNS = {
    "objective_coefficient_solver",
    "objective_coefficient",
    "value",
    "reduced_cost",
}


def _to_text(value):
    """Convert values to robust string representation for coordinate matching."""
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        value = value.item()
    return str(value)


def _series_from_store(store: pd.HDFStore, key: str) -> pd.Series:
    """Return parameter values from HDF as a Series."""
    data = store.get(key)
    if isinstance(data, pd.DataFrame):
        if data.shape[1] == 1:
            return data.iloc[:, 0]
        return data.squeeze(axis=1)
    return data


def _index_names(series: pd.Series, storer) -> list[str]:
    """Extract index names from HDF metadata or fallback to series index names."""
    names_attr = getattr(storer.attrs, "index_names", None)
    if names_attr:
        names = [name for name in names_attr.split(",") if name not in {"", "None"}]
        if names:
            return names

    if isinstance(series.index, pd.MultiIndex):
        names = [name if name is not None else f"level_{i}" for i, name in enumerate(series.index.names)]
    else:
        name = series.index.name if series.index.name is not None else "index"
        names = [name]
    return names


def load_parameter_tables(param_h5: Path) -> list[dict]:
    """Load all parameter tables from param_dict.h5."""
    params = []
    with pd.HDFStore(param_h5, mode="r") as store:
        keys = [key for key in store.keys() if not key.endswith("_units")]
        for key in keys:
            storer = store.get_storer(key)
            series = _series_from_store(store, key)
            if not isinstance(series, pd.Series):
                continue

            names = _index_names(series, storer)
            index_frame = series.index.to_frame(index=False)
            if index_frame.shape[1] != len(names):
                names = [f"level_{i}" for i in range(index_frame.shape[1])]
            index_frame.columns = names
            index_frame = index_frame.apply(lambda col: col.map(_to_text))

            table = index_frame.copy()
            table["param_value"] = series.values

            params.append(
                {
                    "parameter": key.strip("/"),
                    "index_names": names,
                    "table": table,
                }
            )
    return params


def filter_rc_rows(df: pd.DataFrame, only_nonzero_rc: bool, max_rows: int | None) -> pd.DataFrame:
    """Select rows from objective_coefficients_analysis for matching."""
    df = df.copy()
    df["abs_reduced_cost"] = df["reduced_cost"].abs()

    if only_nonzero_rc:
        df = df[df["abs_reduced_cost"] > 0]

    df = df.sort_values("abs_reduced_cost", ascending=False)
    if max_rows is not None:
        df = df.head(max_rows)
    return df.drop(columns=["abs_reduced_cost"])


def match_row_to_parameters(
    row: pd.Series,
    index_columns: list[str],
    parameter_tables: list[dict],
    index_aliases: dict[str, str],
    min_overlap: int,
    top_k: int,
) -> list[dict]:
    """Find candidate parameters for one variable row."""
    row_coords = {}
    for col in index_columns:
        text_value = _to_text(row[col])
        if text_value is None:
            continue
        row_coords[col] = text_value
        if col in index_aliases:
            row_coords[index_aliases[col]] = text_value
    matches = []

    for param in parameter_tables:
        overlap = [dim for dim in param["index_names"] if dim in row_coords]
        if len(overlap) < min_overlap:
            continue

        filtered = param["table"]
        for dim in overlap:
            filtered = filtered[filtered[dim] == row_coords[dim]]
            if filtered.empty:
                break

        if filtered.empty:
            continue

        values = filtered["param_value"]
        sample = values.head(3).tolist()
        match_info = {
            "parameter": param["parameter"],
            "overlap_dims": "|".join(overlap),
            "overlap_count": len(overlap),
            "matched_entries": int(filtered.shape[0]),
            "param_value_sample": repr(sample),
            "param_value_mean": float(pd.to_numeric(values, errors="coerce").mean())
            if pd.to_numeric(values, errors="coerce").notna().any()
            else np.nan,
        }
        matches.append(match_info)

    matches.sort(key=lambda item: (-item["overlap_count"], item["matched_entries"], item["parameter"]))
    return matches[:top_k]


def build_links(
    objective_csv: Path,
    param_h5: Path,
    analysis_json: Path,
    output_csv: Path,
    only_nonzero_rc: bool,
    max_rows: int | None,
    min_overlap: int,
    top_k: int,
) -> None:
    """Create output file mapping reduced-cost rows to candidate parameters."""
    rc_df = pd.read_csv(objective_csv)

    required = {"variable", "reduced_cost", "value", "objective_coefficient"}
    missing = required.difference(rc_df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {objective_csv}: {sorted(missing)}")

    index_columns = [
        col
        for col in rc_df.columns
        if col not in {"variable"}.union(MEASURE_COLUMNS)
    ]

    index_aliases = {}
    if analysis_json.exists():
        with open(analysis_json, "r", encoding="utf-8") as handle:
            analysis = json.load(handle)
        index_aliases = analysis.get("header_data_inputs", {})

    selected_rows = filter_rc_rows(rc_df, only_nonzero_rc=only_nonzero_rc, max_rows=max_rows)
    parameter_tables = load_parameter_tables(param_h5)

    out_rows = []
    for _, row in selected_rows.iterrows():
        candidates = match_row_to_parameters(
            row,
            index_columns=index_columns,
            parameter_tables=parameter_tables,
            index_aliases=index_aliases,
            min_overlap=min_overlap,
            top_k=top_k,
        )

        if not candidates:
            continue

        base = {
            "variable": row["variable"],
            "objective_coefficient": row["objective_coefficient"],
            "value": row["value"],
            "reduced_cost": row["reduced_cost"],
        }
        for col in index_columns:
            base[col] = row[col]

        for candidate in candidates:
            out_rows.append({**base, **candidate})

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(output_csv, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map reduced-cost rows to candidate input parameters."
    )
    parser.add_argument(
        "--output-folder",
        type=Path,
        required=True,
        help="Output folder containing objective_coefficients_analysis.csv and param_dict.h5",
    )
    parser.add_argument(
        "--objective-csv",
        type=Path,
        default=None,
        help="Optional explicit path to objective_coefficients_analysis.csv",
    )
    parser.add_argument(
        "--param-h5",
        type=Path,
        default=None,
        help="Optional explicit path to param_dict.h5",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Optional explicit output path (default: <output-folder>/rc_parameter_links.csv)",
    )
    parser.add_argument(
        "--only-nonzero-rc",
        action="store_true",
        help="Analyze only rows with non-zero reduced cost.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional limit of analyzed objective rows (after filtering/sorting).",
    )
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=1,
        help="Minimum number of shared index dimensions to keep a parameter candidate.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Maximum number of parameter candidates per reduced-cost row.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_folder = args.output_folder

    objective_csv = args.objective_csv or output_folder / "objective_coefficients_analysis.csv"
    param_h5 = args.param_h5 or output_folder / "param_dict.h5"
    analysis_json = output_folder / "analysis.json"
    output_csv = args.output_csv or output_folder / "rc_parameter_links.csv"

    if not objective_csv.exists():
        raise FileNotFoundError(f"Objective CSV not found: {objective_csv}")
    if not param_h5.exists():
        raise FileNotFoundError(f"Parameter HDF not found: {param_h5}")

    build_links(
        objective_csv=objective_csv,
        param_h5=param_h5,
        analysis_json=analysis_json,
        output_csv=output_csv,
        only_nonzero_rc=args.only_nonzero_rc,
        max_rows=args.max_rows,
        min_overlap=args.min_overlap,
        top_k=args.top_k,
    )
    print(f"Wrote parameter links to: {output_csv}")


if __name__ == "__main__":
    main()
