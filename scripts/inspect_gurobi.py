from pathlib import Path

import pandas as pd

from zen_garden.runner import run


def main():
	dataset_name = "5_multiple_time_steps_per_year"

	# Runs ZEN-garden including postprocessing (reduced costs are written there).
	opt = run(config="./config.json", dataset=dataset_name)
	grb = opt.model.solver_model

	print("Gurobi stats:")
	print(
		f"NumVars={grb.NumVars}, NumConstrs={grb.NumConstrs}, "
		f"Runtime={grb.Runtime}, Status={grb.Status}"
	)

	lp_path = Path("my_model.lp")
	grb.write(str(lp_path))
	print(f"LP written to: {lp_path.resolve()}")

	output_dir = Path("outputs") / dataset_name
	rc_h5 = output_dir / "reduced_costs_dict.h5"
	cap_csv = output_dir / "capacity_addition_analysis.csv"

	print("\nPostprocessing outputs:")
	print(f"Reduced costs HDF5: {rc_h5.resolve()}")
	print(f"Capacity addition CSV: {cap_csv.resolve()}")

	if rc_h5.exists():
		with pd.HDFStore(rc_h5, mode="r") as store:
			keys = store.keys()
			print(f"HDF keys ({len(keys)} total):")
			for key in keys[:10]:
				print(f"  - {key}")
			if len(keys) > 10:
				print("  - ...")
	else:
		print("Reduced costs HDF5 file not found.")

	if cap_csv.exists():
		df = pd.read_csv(cap_csv)
		if "reduced_cost" in df.columns:
			non_null = int(df["reduced_cost"].notna().sum())
			print(
				f"capacity_addition_analysis.csv contains 'reduced_cost' "
				f"with {non_null} non-null rows."
			)
		else:
			print("No 'reduced_cost' column found in capacity_addition_analysis.csv")
	else:
		print("capacity_addition_analysis.csv not found.")


if __name__ == "__main__":
	main()
