"""Class is defining the postprocessing of the results.
The class takes as inputs the optimization problem (model) and the system
configurations (system). The class contains methods to read the results and
save them in a result dictionary (resultDict).
"""

import json
import logging
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pint
import xarray as xr
import yaml
from filelock import FileLock
from pydantic import BaseModel
from tables import NaturalNameWarning

from ..optimization_setup import OptimizationSetup

# Warnings
warnings.filterwarnings("ignore", category=NaturalNameWarning)


class Postprocess:
    """Class is defining the postprocessing of the results."""

    def __init__(
        self,
        optimization_setup: OptimizationSetup,
        scenarios,
        model_name,
        subfolder=None,
        scenario_name=None,
        param_map=None,
    ):
        """Postprocessing of the results of the optimization.

        :param model: optimization model
        :param model_name: The name of the model used to name the output folder
        :param subfolder: The subfolder used for the results
        :param scenario_name: The name of the current scenario
        :param param_map: A dictionary mapping the parameters to the scenario names
        """
        logging.info("--- Postprocess results ---")
        # get the necessary stuff from the model
        self.optimization_setup = optimization_setup
        self.model = optimization_setup.model
        self.scenarios = scenarios
        self.system = optimization_setup.system
        self.analysis = optimization_setup.analysis
        self.solver = optimization_setup.solver
        self.energy_system = optimization_setup.energy_system
        self.params = optimization_setup.parameters
        self.vars = optimization_setup.variables
        self.sets = optimization_setup.sets
        self.constraints = optimization_setup.constraints
        self.param_map = param_map
        self.scaling = optimization_setup.scaling

        # get name or directory
        self.model_name = model_name
        self.name_dir = Path(self.analysis.folder_output).joinpath(self.model_name)

        # deal with the subfolder
        self.subfolder = subfolder
        # here we make use of the fact that None and "" both evaluate to
        # False but any non-empty string doesn't
        if subfolder != Path(""):
            # check if mf within scenario analysis
            if isinstance(self.subfolder, tuple):
                scenario_dir = self.name_dir.joinpath(self.subfolder[0])
                os.makedirs(scenario_dir, exist_ok=True)
                mf_in_scenario_dir = self.subfolder[0].joinpath(self.subfolder[1])
                self.name_dir = self.name_dir.joinpath(mf_in_scenario_dir)
            else:
                self.name_dir = self.name_dir.joinpath(self.subfolder)
        # create the output directory
        os.makedirs(self.name_dir, exist_ok=True)

        # check if we should overwrite output
        self.overwrite = self.analysis.overwrite_output
        # get the compression param
        self.output_format = self.analysis.output_format

        # save everything
        self.save_sets()
        self.save_param()
        self.save_var()
        self.save_duals()
        self.save_reduced_costs()
        self.save_capacity_addition_analysis()
        self.save_boundary_shadow_prices()
        self.save_system()
        self.save_analysis()
        self.save_scenarios()
        self.save_solver()
        self.save_unit_definitions()
        self.save_sequence_time_steps(scenario=scenario_name)
        self.save_param_map()
        if self.solver.run_diagnostics:
            self.save_benchmarking_data()

    def write_file(self, name, dictionary, format=None, mode="w"):
        """Writes the dictionary to file as json, if compression attribute is
        True, the serialized json is compressed and saved as binary file.

        Args:
            name: Filename without extension
            dictionary: The dictionary to save
            format: Force the format to use, if None use output_format attribute
                of instance
            mode: Writing mode for python file. The two options are 'w' and
                'a'. The former create a new file while the latter will append
                to an existing file. Appending files is currently only supported
                for h5 files.
        """
        if isinstance(dictionary, BaseModel):
            dictionary = dictionary.model_dump()

        # check whether valid mode
        if mode not in ["a", "w"]:
            ValueError(
                f"Invalid file write mode {mode} (valid options are 'a' or " "'w')."
            )

        # set the format
        if format is None:
            format = self.output_format

        # only allow append mode for h5 files
        if mode == "a" and format != "h5":
            raise ValueError(
                f"Write mode {mode} not available for output format {format}. "
                "If include_operation_only_phase = true, outputs must be saved "
                "in h5 files."
            )

        if format == "yml":
            # serialize to string
            serialized_dict = yaml.dump(dictionary)

            # prep output file
            f_name = f"{name}.yml"
            f_mode = "w"

            # write if necessary
            if self.overwrite or not os.path.exists(f_name):
                with FileLock(f_name + ".lock").acquire(timeout=300):
                    with open(f_name, f_mode) as outfile:
                        outfile.write(serialized_dict)

        elif format == "json":
            # serialize to string

            serialized_dict = json.dumps(dictionary, indent=2)

            # write normal json
            f_name = f"{name}.json"
            f_mode = "w+"

            # write if necessary
            if self.overwrite or not os.path.exists(f_name):
                with FileLock(f_name + ".lock").acquire(timeout=300):
                    with open(f_name, f_mode) as outfile:
                        outfile.write(serialized_dict)

        elif format == "h5":
            f_name = f"{name}.h5"
            with FileLock(f_name + ".lock").acquire(timeout=300):
                self._write_h5_file(f_name, dictionary, mode)

        elif format == "txt":
            f_name = f"{name}.txt"
            f_mode = "w+"

            # write if necessary
            if self.overwrite or not os.path.exists(f_name):
                with FileLock(f_name + ".lock").acquire(timeout=300):
                    with open(f_name, f_mode, encoding="utf-8") as outfile:
                        outfile.write(dictionary)
        else:
            raise AssertionError(
                f"The specified output format {format}, chosen in the config, "
                "is not supported"
            )

    def save_benchmarking_data(self):
        """Saves the benchmarking data to a json file."""
        # initialize dictionary
        benchmarking_data = dict()
        # get the benchmarking data
        benchmarking_data["objective_value"] = self.model.objective.value
        if self.solver.name == "gurobi":
            benchmarking_data["solving_time"] = self.model.solver_model.Runtime
            if "Method" in self.solver.solver_options:
                if self.solver.solver_options["Method"] == 2:
                    benchmarking_data["number_iterations"] = (
                        self.model.solver_model.BarIterCount
                    )
                else:
                    benchmarking_data["number_iterations"] = (
                        self.model.solver_model.IterCount
                    )
            benchmarking_data["solver_status"] = self.model.solver_model.Status
            benchmarking_data["number_constraints"] = self.model.solver_model.NumConstrs
            benchmarking_data["number_variables"] = self.model.solver_model.NumVars
        elif self.solver.name == "highs":
            benchmarking_data["solver_status"] = (
                self.model.solver_model.getModelStatus().name
            )
            benchmarking_data["solving_time"] = self.model.solver_model.getRunTime()
            benchmarking_data["number_iterations"] = (
                self.model.solver_model.getInfo().simplex_iteration_count
            )
            benchmarking_data["number_constraints"] = (
                self.model.solver_model.getNumRow()
            )
            benchmarking_data["number_variables"] = self.model.solver_model.getNumCol()
        else:
            logging.info(
                f"Saving benchmarking data for solver {self.solver.name} has "
                "not been implemented yet"
            )

        benchmarking_data["scaling_time"] = self.scaling.scaling_time
        # get numerical range
        range_lhs, range_rhs = self.scaling.print_numerics(
            0, no_scaling=False, benchmarking_output=True
        )
        benchmarking_data["numerical_range_lhs"] = range_lhs
        benchmarking_data["numerical_range_rhs"] = range_rhs
        fname = self.name_dir.joinpath("benchmarking")
        self.write_file(fname, benchmarking_data, format="json")

    def save_sets(self):
        """Saves the Set values to a json file which can then be
        post-processed immediately or loaded and postprocessed at some
        other time.
        """
        # dataframe serialization
        data_frames = {}
        for set in self.sets:
            if not set.is_indexed():
                continue
            vals = set.data
            index_name = [set.name]

            # if the returned dict is emtpy we create a nan value
            if len(vals) == 0:
                indices = pd.Index(data=[], name=index_name[0])
                data = []
            else:
                indices = list(vals.keys())
                data = list(vals.values())
                data_strings = []
                for tpl in data:
                    string = ""
                    for ind, t in enumerate(tpl):
                        if ind == len(tpl) - 1:
                            string += str(t)
                        else:
                            string += str(t) + ","
                    data_strings.append(string)
                data = data_strings

                # create a multi index if necessary
                if len(indices) >= 1 and isinstance(indices[0], tuple):
                    if len(index_name) == len(indices[0]):
                        indices = pd.MultiIndex.from_tuples(indices, names=index_name)
                    else:
                        indices = pd.MultiIndex.from_tuples(indices)
                else:
                    if len(index_name) == 1:
                        indices = pd.Index(data=indices, name=index_name[0])
                    else:
                        indices = pd.Index(data=indices)

            # create dataframe
            df = pd.DataFrame(data=data, columns=["value"], index=indices)
            # update dict
            doc = self.sets.docs[set.name]
            data_frames[index_name[0]] = self._transform_df(df, doc)

        self.write_file(self.name_dir.joinpath("set_dict"), data_frames)

    def save_param(self):
        """Saves the Param values to a json file which can then be
        post-processed immediately or loaded and postprocessed at some other
        time.
        """
        if not self.solver.save_parameters:
            logging.info("Parameters are not saved")
            return

        # dataframe serialization
        data_frames = {}
        for param in self.params.docs.keys():
            if (
                self.solver.selected_saved_parameters
                and param not in self.solver.selected_saved_parameters
            ):
                continue
            # get the values
            vals = getattr(self.params, param)
            doc = self.params.docs[param]
            units = self.params.units[param]
            index_list = self.get_index_list(doc)
            # data frame
            if isinstance(vals, xr.DataArray):
                df = vals.to_dataframe("value").dropna()
            # we have a scalar
            else:
                df = pd.DataFrame(data=[vals], columns=["value"])

            # rename the index
            if len(df.index.names) == len(index_list):
                df.index.names = index_list

            units = self._unit_df(units, df.index)
            # update dict
            data_frames[param] = self._transform_df(df, doc, units)

        # write to json
        self.write_file(self.name_dir.joinpath("param_dict"), data_frames)

    def save_var(self):
        """Saves the variable values to a json file which can then be
        post-processed immediately or loaded and postprocessed at some other
        time.
        """
        # dataframe serialization
        data_frames = {}
        for name, arr in self.model.solution.items():

            # skip variables not selected to be saved
            if (
                self.solver.selected_saved_variables
                and name not in self.solver.selected_saved_variables
            ):
                continue

            # extract doc information
            if name in self.vars.docs:
                doc = self.vars.docs[name]
                units = self.vars.units[name]
                index_list = self.get_index_list(doc)
            elif name.startswith("sos2_var"):
                continue
            else:
                index_list = []
                doc = None
                units = None

            # create dataframe
            df = arr.to_dataframe("value").dropna()

            # rename the index
            if len(df.index.names) == len(index_list):
                df.index.names = index_list

            units = self._unit_df(units, df.index)

            # transform the dataframe to a json string and load it into the
            # dictionary as dict
            data_frames[name] = self._transform_df(df, doc, units)

        # write file
        self.write_file(self.name_dir.joinpath("var_dict"), data_frames, mode="w")

    def save_duals(self):
        """Saves the dual variable values to a h5 file."""
        if not self.solver.save_duals:
            logging.info("Duals are not saved")
            return

        # dataframe serialization
        data_frames = {}
        for name in self.model.constraints:

            arr = self.model.constraints[name].dual

            # skip variables not selected to be saved
            if (
                self.solver.selected_saved_duals
                and name not in self.solver.selected_saved_duals
            ):
                continue

            # extract doc information
            if name in self.constraints.docs:
                doc = self.constraints.docs[name]
                index_list = self.get_index_list(doc)
            else:
                index_list = []
                doc = None

            # rescale
            if self.solver.use_scaling:
                cons_labels = self.model.constraints[name].labels.data
                scaling_factor = self.optimization_setup.scaling.D_r_inv[cons_labels]
                arr = arr * scaling_factor
            # create dataframe
            if len(arr.shape) > 0:
                df = arr.to_series().dropna()
            else:
                df = pd.DataFrame(data=[arr.values], columns=["value"])

            # rename the index
            if len(df.index.names) == len(index_list):
                df.index.names = index_list

            # we transform the dataframe to a json string and load it into the
            # dictionary as dict
            data_frames[name] = self._transform_df(df, doc)

        # write file
        self.write_file(self.name_dir.joinpath("dual_dict"), data_frames, mode="w")

    def save_reduced_costs(self):
        """Saves the reduced cost values of variables to a h5 file."""
        if self.solver.name != "gurobi":
            logging.info("Reduced costs are only supported for gurobi solver")
            return

        if not self.solver.save_reduced_costs:
            logging.info("Reduced costs are not saved")
            return

        # dataframe serialization
        data_frames = {}
        for name in self.model.variables:

            # skip variables not selected to be saved
            if (
                self.solver.selected_saved_reduced_costs
                and name not in self.solver.selected_saved_reduced_costs
            ):
                continue

            # get reduced costs from solver
            try:
                arr = self.model.variables[name].get_solver_attribute("RC")
            except Exception as e:
                logging.warning(
                    f"Could not retrieve reduced costs for variable {name}: {e}"
                )
                continue

            # extract doc information
            if name in self.vars.docs:
                doc = self.vars.docs[name]
                index_list = self.get_index_list(doc)
            else:
                index_list = []
                doc = None

            # rescale
            if self.solver.use_scaling:
                var_labels = self.model.variables[name].labels.data
                scaling_factor = self.optimization_setup.scaling.D_c_inv[var_labels]
                arr = arr * scaling_factor

            # create dataframe
            if len(arr.shape) > 0:
                df = arr.to_series().dropna()
            else:
                df = pd.DataFrame(data=[arr.values], columns=["value"])

            # rename the index
            if len(df.index.names) == len(index_list):
                df.index.names = index_list

            # we transform the dataframe to a json string and load it into the
            # dictionary as dict
            data_frames[name] = self._transform_df(df, doc)

        # write file
        self.write_file(
            self.name_dir.joinpath("reduced_costs_dict"), data_frames, mode="w"
        )

    def _compute_rc_capex_equivalent(self, df):
        """Computes the capex-equivalent reduced cost from constraint_technology_lifetime duals.

        Uses the LP optimality condition for capacity_addition at its lower bound:

            rc_capex_equiv = capex_specific - elec_value / scaling

        where:
            elec_value = sum(-dual_lifetime[y] for y in pay_years)
            scaling    = annuity_factor * sum(discount_factor[y] for y in pay_years)

        With Primal Simplex (Method=0) the duals are exact LP duals — no approximation.

        Returns a list of rc values in internal model units, one per row of df.
        Divide by fraction_year to get Euro/kW (see save_capacity_addition_analysis).
        """
        params = self.optimization_setup.parameters
        system = self.optimization_setup.system
        es = self.optimization_setup.energy_system

        r = float(params.discount_rate)
        dy = system.interval_between_years
        years = list(es.set_time_steps_yearly)
        first_year = years[0]
        last_year_entire = es.set_time_steps_yearly_entire_horizon[-1]

        # Discount factor per planning year — matches ZEN-garden's energy_system.py formula
        discount_factors = {}
        for y in years:
            iv = 1 if y == last_year_entire else dy
            discount_factors[y] = sum(
                (1.0 / (1.0 + r)) ** (dy * (y - first_year) + i)
                for i in range(iv)
            )

        # Exact LP duals from constraint_technology_lifetime (negative = capacity has value)
        dual_arr = self.model.constraints["constraint_technology_lifetime"].dual
        if self.solver.use_scaling:
            cons_labels = self.model.constraints["constraint_technology_lifetime"].labels.data
            dual_arr = dual_arr * self.optimization_setup.scaling.D_r_inv[cons_labels]
        dual_series = dual_arr.to_series().dropna()

        # Internal capex_specific lookup: (tech, ctype, node, year) -> value
        capex_lookup = {}
        for param_name in ["capex_specific_conversion", "capex_specific_storage",
                           "capex_specific_transport"]:
            p = getattr(params, param_name, None)
            if p is None:
                continue
            try:
                for idx, val in p.to_series().dropna().items():
                    if not isinstance(idx, tuple):
                        idx = (idx,)
                    tech_name, year_val, node_val = idx[0], idx[-1], idx[-2]
                    ctype_val = idx[1] if len(idx) == 4 else None
                    capex_lookup.setdefault((tech_name, node_val, year_val), float(val))
                    capex_lookup.setdefault((tech_name, ctype_val, node_val, year_val), float(val))
            except Exception:
                continue

        tech_cache = {}
        result = []

        for idx in df.index:
            tech, ctype, node, y_inv = idx[0], idx[1], idx[2], idx[3]
            try:
                if tech not in tech_cache:
                    lt = float(np.squeeze(
                        params.depreciation_time.sel(set_technologies=tech).values
                    ))
                    af = ((1.0 + r) ** lt * r) / ((1.0 + r) ** lt - 1.0) if r != 0 else 1.0 / lt
                    tech_cache[tech] = (af, max(int(np.floor(lt / dy)), 1))
                af, n_periods = tech_cache[tech]

                pay_years = [y for y in years if y_inv <= y <= y_inv + n_periods - 1]
                discount_sum = sum(discount_factors[y] for y in pay_years)
                scaling = af * discount_sum
                if scaling <= 0:
                    result.append(np.nan)
                    continue

                cs = capex_lookup.get((tech, ctype, node, y_inv),
                     capex_lookup.get((tech, node, y_inv), np.nan))
                if np.isnan(cs):
                    result.append(np.nan)
                    continue

                elec_value = 0.0
                for y in pay_years:
                    mask = (
                        (dual_series.index.get_level_values(0) == tech)
                        & (dual_series.index.get_level_values(1) == ctype)
                        & (dual_series.index.get_level_values(2) == node)
                        & (dual_series.index.get_level_values(3) == y)
                    )
                    matches = dual_series[mask]
                    if matches.empty:
                        elec_value = np.nan
                        break
                    elec_value += -float(matches.iloc[0])

                result.append(np.nan if np.isnan(elec_value) else cs - elec_value / scaling)

            except Exception:
                result.append(np.nan)

        return result

    def save_capacity_addition_analysis(self):
        """Saves capacity_addition values and capex-equivalent reduced costs to CSV.

        Output: <output_dir>/capacity_addition_analysis.csv

        Columns:
          value                          optimal capacity addition [GW]
          reduced_cost                   Gurobi RC attribute [model units]
          rc_capex_equivalent            dual-based RC [model units]
          rc_capex_equivalent_input_units dual-based RC [Euro/kW]

        rc_capex_equivalent_input_units answers:
          "By how much must capex decrease for this technology to become optimal?"
          = 0 for built technologies, > 0 for unbuilt technologies.

        Requires Primal Simplex (Method=0) for exact duals. See main_rc.py.
        """
        if "capacity_addition" not in self.model.variables:
            logging.info("capacity_addition variable not found — skipping RC analysis")
            return

        var_values = self.model.solution["capacity_addition"]
        df = var_values.to_series().dropna().to_frame("value")
        if df.empty:
            logging.warning("No capacity_addition data to save")
            return

        unit = self.vars.units.get("capacity_addition", "") if hasattr(self.vars, "units") else ""
        df["unit"] = unit

        # Gurobi RC attribute (exact with Simplex, mu/x noise with Barrier+no Crossover)
        if self.solver.name == "gurobi":
            try:
                rc_arr = self.model.variables["capacity_addition"].get_solver_attribute("RC")
                if self.solver.use_scaling:
                    var_labels = self.model.variables["capacity_addition"].labels.data
                    rc_arr = rc_arr * self.optimization_setup.scaling.D_c_inv[var_labels]
                df["reduced_cost"] = rc_arr.to_series()
            except Exception as e:
                logging.debug(f"Could not retrieve Gurobi RC: {e}")
                df["reduced_cost"] = np.nan
        else:
            df["reduced_cost"] = np.nan

        # Dual-based capex-equivalent RC — primary reliable metric
        try:
            df["rc_capex_equivalent"] = self._compute_rc_capex_equivalent(df)
        except Exception as e:
            logging.warning(f"Could not compute rc_capex_equivalent: {e}")
            df["rc_capex_equivalent"] = np.nan

        # Convert to input units (Euro/kW): invert the fraction_year scaling
        # ZEN-garden stores capex_specific internally as input_value * fraction_year,
        # so dividing by fraction_year recovers the original Euro/kW unit.
        try:
            fraction_year = (
                self.system.unaggregated_time_steps_per_year
                / self.system.total_hours_per_year
            )
            df["rc_capex_equivalent_input_units"] = df["rc_capex_equivalent"] / fraction_year
        except Exception as e:
            logging.warning(f"Could not compute rc_capex_equivalent_input_units: {e}")
            df["rc_capex_equivalent_input_units"] = np.nan

        try:
            df["rc_reliability"] = self._compute_rc_reliability(df)
        except Exception as e:
            logging.warning(f"Could not compute rc_reliability: {e}")
            df["rc_reliability"] = "unknown"

        df = df[["unit", "value", "reduced_cost",
                 "rc_capex_equivalent", "rc_capex_equivalent_input_units",
                 "rc_reliability"]]

        csv_file = self.name_dir.joinpath("capacity_addition_analysis.csv")
        df.to_csv(csv_file)
        logging.info(f"Capacity addition analysis saved to {csv_file}")

    def _compute_rc_reliability(self, df):
        """Classifies RC reliability per technology row based on OPEX/CAPEX ratio and fuel inputs.

        Returns a list of strings: 'high', 'medium', 'low', or 'unknown'.

        high   — CAPEX-dominated, no expensive fuel input (opex_ratio < 0.3)
        medium — Moderate OPEX or electricity-only input with higher fixed OPEX
        low    — Expensive fuel input (gas, coal, oil, biomass, ...) contaminates dual
        unknown — Parameters missing or not computable
        """
        params = self.optimization_setup.parameters
        r = float(params.discount_rate)

        FUEL_CARRIERS = {
            "natural_gas", "hard_coal", "lignite", "lignite_coal", "oil", "diesel", "petrol",
            "gasoline", "kerosene", "naphtha", "biomass", "waste", "ammonia", "methanol",
            "hydrogen",
        }
        CHEAP_FUEL = {"uranium"}
        ELEC_CARRIERS = {"electricity"}

        def annuity(lt):
            if not lt or lt <= 0:
                return float("nan")
            return (r * (1 + r) ** lt) / ((1 + r) ** lt - 1)

        tech_cache = {}
        result = []

        for idx in df.index:
            tech = idx[0]
            try:
                if tech not in tech_cache:
                    lt = float(np.squeeze(
                        params.depreciation_time.sel(set_technologies=tech).values
                    ))
                    af = annuity(lt)

                    # CAPEX (try conversion, storage, transport)
                    capex = None
                    for attr in ["capex_specific_conversion", "capex_specific_storage",
                                 "capex_per_distance_transport"]:
                        p = getattr(params, attr, None)
                        if p is None:
                            continue
                        try:
                            capex = float(np.squeeze(
                                p.sel(set_technologies=tech).mean().values
                            ))
                            break
                        except Exception:
                            continue

                    opex_f = None
                    p = getattr(params, "opex_specific_fixed", None)
                    if p is not None:
                        try:
                            opex_f = float(np.squeeze(
                                p.sel(set_technologies=tech).mean().values
                            ))
                        except Exception:
                            pass

                    capex_ann = capex * af if (capex and not np.isnan(af)) else float("nan")
                    opex_ratio = (opex_f / capex_ann
                                  if opex_f is not None and capex_ann > 0
                                  and not np.isnan(capex_ann)
                                  else float("nan"))

                    # Input carriers
                    input_carriers = set()
                    try:
                        es = self.optimization_setup.energy_system
                        for carrier in es.set_carriers:
                            if hasattr(es, "set_input_carriers"):
                                if tech in es.set_input_carriers and carrier in es.set_input_carriers[tech]:
                                    input_carriers.add(carrier)
                    except Exception:
                        pass

                    fuel_flag = bool(input_carriers & FUEL_CARRIERS)
                    cheap_fuel_flag = bool((input_carriers & CHEAP_FUEL) and not fuel_flag)
                    elec_flag = bool(input_carriers & ELEC_CARRIERS)

                    tech_cache[tech] = (opex_ratio, fuel_flag, cheap_fuel_flag, elec_flag)

                opex_ratio, fuel_flag, cheap_fuel_flag, elec_flag = tech_cache[tech]

                if np.isnan(opex_ratio):
                    rel = "unknown"
                elif fuel_flag:
                    rel = "low"
                elif cheap_fuel_flag:
                    rel = "medium"
                elif elec_flag and opex_ratio > 0.35:
                    rel = "medium"
                elif opex_ratio < 0.3:
                    rel = "high"
                elif opex_ratio < 0.5:
                    rel = "medium"
                else:
                    rel = "low"

                result.append(rel)

            except Exception:
                result.append("unknown")

        return result

    # ---------------------------------------------------------------------------
    # Boundary shadow prices
    # ---------------------------------------------------------------------------

    # Constraints that represent system boundaries, with metadata
    _BOUNDARY_CONSTRAINTS = {
        "constraint_carbon_emissions_annual_limit": {
            "cluster": "CO2_cap",
            "description": "Annual CO2 emissions limit",
            "shadow_price_unit": "Euro/tCO2",
        },
        "constraint_carbon_emissions_budget": {
            "cluster": "CO2_cap",
            "description": "Cumulative CO2 budget over horizon",
            "shadow_price_unit": "Euro/tCO2",
        },
        "constraint_technology_capacity_limit_not_reached": {
            "cluster": "capacity_limit",
            "description": "Technology/node capacity upper bound (limit not yet reached)",
            "shadow_price_unit": "Euro/GW",
        },
        "constraint_technology_capacity_limit_reached": {
            "cluster": "capacity_limit",
            "description": "Technology/node capacity upper bound (limit reached)",
            "shadow_price_unit": "Euro/GW",
        },
        "constraint_availability_import": {
            "cluster": "import_availability",
            "description": "Hourly carrier import limit from outside system",
            "shadow_price_unit": "Euro/GWh",
        },
        "constraint_availability_export": {
            "cluster": "import_availability",
            "description": "Hourly carrier export limit outside system",
            "shadow_price_unit": "Euro/GWh",
        },
        "constraint_availability_import_yearly": {
            "cluster": "import_availability",
            "description": "Annual carrier import limit from outside system",
            "shadow_price_unit": "Euro/GWh",
        },
        "constraint_availability_export_yearly": {
            "cluster": "import_availability",
            "description": "Annual carrier export limit outside system",
            "shadow_price_unit": "Euro/GWh",
        },
        "constraint_technology_diffusion_limit": {
            "cluster": "diffusion_limit",
            "description": "Technology annual capacity addition growth rate cap",
            "shadow_price_unit": "Euro/GW",
        },
        "constraint_technology_diffusion_limit_total": {
            "cluster": "diffusion_limit",
            "description": "Global technology deployment growth rate cap",
            "shadow_price_unit": "Euro/GW",
        },
    }

    def save_boundary_shadow_prices(self):
        """Exports shadow prices of system boundary constraints to CSV.

        Only constraints with non-zero (binding) duals are included.

        Output: <output_dir>/boundary_shadow_prices.csv

        Columns:
          constraint        constraint name
          cluster           boundary type (CO2_cap, capacity_limit, import_availability,
                            diffusion_limit)
          description       plain-text explanation
          shadow_price_unit unit of shadow price in input terms
          shadow_price      dual value [model units]
          shadow_price_input_units  dual value rescaled to input units
          ... (index columns from the constraint)
        """
        if not self.solver.save_duals:
            logging.info("Duals not saved — skipping boundary shadow price export")
            return

        fraction_year = None
        try:
            fraction_year = (
                self.system.unaggregated_time_steps_per_year
                / self.system.total_hours_per_year
            )
        except Exception:
            pass

        all_rows = []

        for con_name, meta in self._BOUNDARY_CONSTRAINTS.items():
            if con_name not in self.model.constraints:
                continue

            arr = self.model.constraints[con_name].dual
            if self.solver.use_scaling:
                try:
                    labels = self.model.constraints[con_name].labels.data
                    arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
                except Exception:
                    pass

            try:
                series = arr.to_series().dropna()
            except Exception:
                continue

            # Keep only binding constraints (non-zero dual)
            series = series[series != 0]
            if series.empty:
                continue

            for idx, dual_val in series.items():
                if not isinstance(idx, tuple):
                    idx = (idx,)

                # Shadow price in input units: capacity constraints → divide by fraction_year
                # CO2 constraints are already in Euro/tCO2 (no time-step scaling needed)
                if fraction_year and meta["cluster"] != "CO2_cap":
                    sp_input = dual_val / fraction_year
                else:
                    sp_input = dual_val

                row = {
                    "constraint":              con_name,
                    "cluster":                 meta["cluster"],
                    "description":             meta["description"],
                    "shadow_price_unit":       meta["shadow_price_unit"],
                    "shadow_price":            dual_val,
                    "shadow_price_input_units": sp_input,
                }
                # Unpack index into named columns
                for i, v in enumerate(idx):
                    row[f"index_{i}"] = v

                all_rows.append(row)

        if not all_rows:
            logging.info("No binding boundary constraints found — boundary_shadow_prices.csv not written")
            return

        import pandas as pd
        out_df = pd.DataFrame(all_rows)
        csv_file = self.name_dir.joinpath("boundary_shadow_prices.csv")
        out_df.to_csv(csv_file, index=False)
        logging.info(f"Boundary shadow prices saved to {csv_file} ({len(all_rows)} binding constraints)")

    def save_system(self):
        """Saves the system dict as json."""
        if self.system.use_rolling_horizon:
            fname = self.name_dir.parent.joinpath("system")
        else:
            fname = self.name_dir.joinpath("system")
        self.write_file(fname, self.system, format="json")

    def save_analysis(self):
        """Saves the analysis dict as json."""
        if self.system.use_rolling_horizon:
            fname = self.name_dir.parent.joinpath("analysis")
        else:
            fname = self.name_dir.joinpath("analysis")
        # remove cwd path part to avoid saving the absolute path
        if os.path.isabs(self.analysis.dataset):
            cwd = os.getcwd()
            self.analysis.dataset = os.path.relpath(self.analysis.dataset, cwd)
            self.analysis.folder_output = os.path.relpath(
                self.analysis.folder_output, cwd
            )
        self.write_file(fname, self.analysis, format="json")

    def save_solver(self):
        """Saves the solver dict as json."""
        # This we only need to save once
        if self.system.use_rolling_horizon:
            fname = self.name_dir.parent.joinpath("solver")
        else:
            fname = self.name_dir.joinpath("solver")

        # remove cwd path part to avoid saving the absolute path
        if os.path.isabs(self.solver.solver_dir):
            cwd = os.getcwd()
            self.solver.solver_dir = os.path.relpath(self.solver.solver_dir, cwd)
        # save
        self.write_file(fname, self.solver, format="json")

    def save_scenarios(self):
        """Saves the scenario dict as json."""
        # only save the scenarios at the highest level
        root_dir = Path(self.analysis.folder_output).joinpath(self.model_name)
        fname = root_dir.joinpath("scenarios")
        self.write_file(fname, self.scenarios, format="json")

    def save_unit_definitions(self):
        """Saves the user-defined units as txt."""
        if self.system.use_rolling_horizon:
            fname = self.name_dir.parent.joinpath("unit_definitions")
        else:
            fname = self.name_dir.joinpath("unit_definitions")

        lines = []
        ureg = self.energy_system.unit_handling.ureg
        # Only save user-defined units (skip base units like 'meter')
        all_units = ureg._units
        default_units = pint.UnitRegistry()._units
        user_units = list(set(all_units.items()).difference(default_units.items()))
        for _name, unit in user_units:
            if hasattr(unit, "raw") and f"{unit.raw}\n" not in lines:
                lines.append(f"{unit.raw}\n")
        txt = "".join(lines)
        self.write_file(fname, txt, format="txt")

    def save_param_map(self):
        """Saves the param_map dict as yaml."""
        if self.param_map is not None:
            # This we only need to save once
            if (
                self.system.use_rolling_horizon
                and self.system.conduct_scenario_analysis
            ):
                fname = self.name_dir.parent.parent.joinpath("param_map")
            elif self.subfolder != Path(""):
                fname = self.name_dir.parent.joinpath("param_map")
            else:
                fname = self.name_dir.joinpath("param_map")
            self.write_file(fname, self.param_map, format="yml")

    def save_sequence_time_steps(self, scenario=None):
        """Saves the dict_all_sequence_time_steps dict as json.

        :param scenario: name of scenario for which results are postprocessed
        """
        # extract and save sequence time steps, we transform the arrays to lists
        self.dict_sequence_time_steps = self.flatten_dict(
            self.energy_system.time_steps.get_sequence_time_steps_dict()
        )
        self.dict_sequence_time_steps["optimized_time_steps"] = (
            self.optimization_setup.optimized_time_steps
        )
        self.dict_sequence_time_steps["time_steps_operation_duration"] = (
            self.energy_system.time_steps.time_steps_operation_duration
        )
        self.dict_sequence_time_steps["time_steps_storage_duration"] = (
            self.energy_system.time_steps.time_steps_storage_duration
        )
        self.dict_sequence_time_steps["time_steps_storage_level_startend_year"] = (
            self.energy_system.time_steps.time_steps_storage_level_startend_year
        )
        self.dict_sequence_time_steps["time_steps_year2operation"] = (
            self.get_time_steps_year2operation()
        )
        self.dict_sequence_time_steps["time_steps_year2storage"] = (
            self.get_time_steps_year2storage()
        )

        # add the scenario name
        if scenario is not None:
            add_on = f"_{scenario}"
        else:
            add_on = ""

            # This we only need to save once
        if self.system.use_rolling_horizon:
            fname = self.name_dir.parent.joinpath(
                f"dict_all_sequence_time_steps{add_on}"
            )
        else:
            fname = self.name_dir.joinpath(f"dict_all_sequence_time_steps{add_on}")
        dict_sequence_time_steps = self.dict_sequence_time_steps
        dict_formatted = {}
        for k, v in dict_sequence_time_steps.items():
            if isinstance(v, np.ndarray):
                dict_formatted[k] = v.tolist()
            elif isinstance(v, dict):
                dict_formatted[k] = {
                    str(kk): vv.tolist() if isinstance(vv, np.ndarray) else str(vv)
                    for kk, vv in v.items()
                }
            elif isinstance(v, list):
                dict_formatted[k] = v
            else:
                NotImplementedError(f"Type {type(v)} not supported for key {k}")
        self.write_file(fname, dict_formatted, format="json")

    def flatten_dict(self, dictionary):
        """Creates a copy of the dictionary where all numpy arrays are
        recursively flattened to lists such that it can be saved as json file.

        :param dictionary: The input dictionary
        :return: A copy of the dictionary containing lists instead of arrays
        """
        # create a copy of the dict to avoid overwrite
        out_dict = dict()

        # falten all arrays
        for k, v in dictionary.items():
            # transform the key None to 'null'
            if k is None:
                k = "null"

            # recursive call
            if isinstance(v, dict):
                out_dict[k] = self.flatten_dict(v)  # flatten the array to list
            elif isinstance(v, pd.Series):
                # Note: list(v) creates a list of np objects v.tolist() not
                out_dict[k] = v.values.tolist()
            # take as is
            else:
                out_dict[k] = v

        return out_dict

    def get_index_list(self, doc):
        """Get index list from docstring.

        :param doc: docstring
        :return: index list
        """
        split_doc = doc.split(";")
        for string in split_doc:
            if "dims" in string:
                break
        string = string.replace("dims:", "")
        index_list = string.split(",")
        index_list_final = []
        for index in index_list:
            if index in self.analysis.header_data_inputs.keys():
                index_list_final.append(
                    self.analysis.header_data_inputs[index]
                )  # else:  #     pass  #     # index_list_final.append(index)
        return index_list_final

    def get_time_steps_year2operation(self):
        """Returns a HDF5-Serializable version of the
        dict_time_steps_year2operation dictionary.
        """
        ans = {}
        for (
            year,
            time_steps,
        ) in self.energy_system.time_steps.time_steps_year2operation.items():
            ans[str(year)] = time_steps
        return ans

    def get_time_steps_year2storage(self):
        """Returns a HDF5-Serializable version of the
        dict_time_steps_year2storage dictionary.
        """
        ans = {}
        for (
            year,
            time_steps,
        ) in self.energy_system.time_steps.time_steps_year2storage.items():
            ans[str(year)] = time_steps
        return ans

    def _transform_df(self, df, doc, units=None):
        """We transform the dataframe to a json string and load it into the
        dictionary as dict.

        :param df: dataframe
        :param doc: doc string
        :param units: units
        :return: dictionary
        """
        if self.output_format == "h5":
            if units is not None:
                dataframe = {"dataframe": df, "docstring": doc, "units": units}
            else:
                dataframe = {"dataframe": df, "docstring": doc}
        else:
            raise AssertionError(
                f"The specified output format {self.output_format}, chosen in "
                "the config, is not supported"
            )
        return dataframe

    def _doc_to_df(self, doc):
        """Transforms the docstring to a dataframe.

        :param doc: doc string
        :return: pd.Series of the docstring
        """
        if doc is not None:
            return (
                pd.Series(doc.split(";"))
                .str.split(":", expand=True)
                .set_index(0)
                .squeeze()
            )
        else:
            return pd.DataFrame()

    def _unit_df(self, units, index):
        """Transforms the units to a series.

        :param units: units string
        :param index: index of the target dataframe
        :return: pd.Series of the units
        """
        if units is not None:
            if isinstance(units, str):
                return pd.Series(units, index=index)
            elif len(units) == len(index):
                units.index.names = index.names
                return units
            else:
                raise AssertionError(
                    "The length of the units does not match the length of the " "index"
                )
        else:
            return None

    def _write_h5_file(
        self, file_name, dictionary, mode="w", complevel=4, complib="blosc"
    ):
        """Writes the dictionary to a hdf5 file.

        :param file_name: The name of the file
        :param dictionary: The dictionary to save
        :param mode: Writting mode for python file. The two options are 'w' and
            'a'. The former create a new file while the latter will append to an
            existing file.
        """
        if mode == "w" and not self.overwrite and os.path.exists(file_name):
            raise FileExistsError(
                "File already exists. Please set overwrite=True to overwrite "
                "the file."
            )
        with pd.HDFStore(
            file_name, mode=mode, complevel=complevel, complib=complib
        ) as store:
            for key, value in dictionary.items():
                if not isinstance(key, str):
                    raise TypeError("All dictionary keys must be strings!")
                if isinstance(value, dict):
                    input_dict, units, docstring, has_units = self._format_dict(value)
                    if not input_dict["dataframe"].empty:
                        df = input_dict["dataframe"]
                        store.put(key, df, format="table")
                        # add additional attributes
                        index_names = df.index.names
                        index_names = ",".join([str(name) for name in index_names])
                        store.get_storer(key).attrs.docstring = docstring
                        store.get_storer(key).attrs["name"] = key
                        store.get_storer(key).attrs["has_units"] = has_units
                        store.get_storer(key).attrs["index_names"] = index_names
                        if has_units:
                            store.put(key + "_units", units, format="table")
                        # remove "_i_table" to reduce file size
                        try:
                            store.remove(key + "/_i_table")
                            store.remove(key + "_units/_i_table")
                        except KeyError:
                            pass
                else:
                    raise TypeError(f"Type {type(value)} is not supported.")

    @staticmethod
    def _format_dict(input_dict):
        """Format the dictionary to be saved in the hdf file
        :param input_dict: The dictionary to format.
        """
        expected_keys = ["dataframe", "docstring"]
        if "dataframe" in input_dict:
            df = input_dict["dataframe"]
            if not isinstance(df, pd.Series):
                if df.shape[1]:
                    df = df.squeeze(axis=1)
            input_dict["dataframe"] = df
        if "docstring" in input_dict:
            docstring = input_dict["docstring"]
        else:
            docstring = None
        if "units" in input_dict:
            units = input_dict["units"]
            assert isinstance(
                units, pd.Series
            ), f"Units must be a pandas Series, but is {type(units)}"
            df = input_dict["dataframe"]
            assert units.index.intersection(df.index).equals(units.index), (
                f"Units index {units.index} does not match dataframe "
                f"index {df.index}"
            )
            units.name = "units"
            has_units = True
        else:
            has_units = False
            units = None
        if not (
            set(input_dict.keys()) == set(expected_keys)
            or set(input_dict.keys()) == set(expected_keys).union(["units"])
        ):
            raise ValueError(
                f"Expected keys are {expected_keys}, but got " f"{input_dict.keys()}"
            )
        return input_dict, units, docstring, has_units
