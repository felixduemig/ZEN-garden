"""Main entry point for Mean-Variance Optimization runs.

This script demonstrates how to use the mean-variance optimization plugin
to balance NPV minimization with risk (variance) minimization in the
energy system design.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from zen_garden import run
from zen_garden.plugin_system.events import Event, EventPublisher
from zen_garden.postprocess.postprocess import Postprocess
from zen_garden.plugins.mean_variance_optimization.plugin import config as plugin_config


# SETTINGS
on_server = False
example_dataset = False
base = 10e-6
weights = [x * base for x in [25, 50, 75, 100]]
dir_extension = "mean_variance_run"

# PATHS
if on_server:
    root_path = Path("/home/jwiegner/ZEN-models")
else:
    root_path = Path("C:/ZenGardenInput/ZEN-models")

if example_dataset:
    if on_server:
        raise NotImplementedError("Example dataset not available on server.")
    root_path = Path(r"C:\ZenGardenInput\example_datasets")
    os.chdir(root_path)
    dataset = "8_yearly_variation"
else:
    os.chdir(root_path / "data")
    dataset = "Crystal_Ball"

# Create output directory with timestamp
now = datetime.now()
time_str = now.strftime("%Y%m%d-%H%M%S")
result_folder = f"./outputs_{time_str}_{dir_extension}/linear"

if not os.path.exists(result_folder):
    os.makedirs(result_folder)

# Run baseline (linear, no variance term)
with open("./config.json") as f:
    config = json.load(f)

config["solver"]["solver_options"]["LogFile"] = f"{result_folder}/solver.log"

with open("./config.json", "w") as f:
    json.dump(config, f, indent=4)

run(config="./config.json", dataset=dataset, folder_output=result_folder)

# Run with different variance weightings
include_var_for = {
    "capex": ["technology_capex"],
    # "capex_opex": ["capex", "opex"],
    # "capex_opex_import": ["capex", "opex", "import"],
    # "capex_opex_demand": ["capex", "opex", "demand_shedding"]
}

for variance_inclusion in include_var_for.keys():
    for i, weight in enumerate(weights):
        if i == 0:
            result_folder = f"./outputs_{time_str}_{dir_extension}/{variance_inclusion}/lambda_{str(weight)}"
            if not os.path.exists(result_folder):
                os.makedirs(result_folder)

            with open("./config.json") as f:
                config = json.load(f)

            config["plugins"]["mean_variance_optimization"] = {}
            config["plugins"]["mean_variance_optimization"]["weighting_factor"] = weight
            config["plugins"]["mean_variance_optimization"]["include_variances_for"] = include_var_for[variance_inclusion]
            config["solver"]["solver_options"]["LogFile"] = f"{result_folder}/solver.log"

            with open("./config_quadratic.json", "w") as f:
                json.dump(config, f, indent=4)

            optimization_setup = run(
                config="./config_quadratic.json",
                dataset=dataset,
                folder_output=result_folder,
            )
        else:
            result_folder = f"./outputs_{time_str}_{dir_extension}/{variance_inclusion}/lambda_{str(weight)}"
            if not os.path.exists(result_folder):
                os.makedirs(result_folder)

            plugin_config["weighting_factor"] = weight
            optimization_setup.solver.solver_options["LogFile"] = f"{result_folder}/solver.log"
            optimization_setup.solver.solver_dir = result_folder
            optimization_setup.analysis.folder_output = result_folder

            EventPublisher.trigger(
                Event.after_model_construction,
                optimization_setup=optimization_setup
            )

            if optimization_setup.solver.use_scaling:
                optimization_setup.scaling.run_scaling()
            elif (
                optimization_setup.solver.analyze_numerics
                or optimization_setup.solver.run_diagnostics
            ):
                optimization_setup.scaling.analyze_numerics()

            # SOLVE THE OPTIMIZATION PROBLEM
            optimization_setup.solve()

            if optimization_setup.solver.use_scaling:
                optimization_setup.scaling.re_scale()

            # EVALUATE RESULTS
            scenarios = {'': {}}
            subfolder = Path(".")
            model_name = 'Crystal_Ball'
            scenario_name = None
            param_map = None

            # write results
            Postprocess(
                optimization_setup,
                scenarios=scenarios,
                subfolder=subfolder,
                model_name=model_name,
                scenario_name=scenario_name,
                param_map=param_map,
            )

print("Mean-Variance optimization runs completed.")
