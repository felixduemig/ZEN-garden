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
        """Computes the capex-equivalent reduced cost from constraint duals.

        Uses the LP optimality condition for capacity_addition at its lower bound:

            rc_capex_equiv = capex_specific - (elec_value - diff_contribution) / scaling

        where:
            elec_value       = sum(-dual_lifetime[y] for y in pay_years)
            diff_contribution = sum(mu_diff[y] * tdr[y] * kdr[y, y_inv]
                                    for y in years if y > y_inv)
            scaling          = annuity_factor * sum(discount_factor[y] for y in pay_years)

        The diff_contribution captures that capacity_addition[y_inv] appears in all
        *future* diffusion constraints (y > y_inv) as part of the knowledge base, with
        coefficient -tdr[y]*kdr[y,y_inv].  If those constraints are binding their duals
        mu_diff[y] != 0 and contribute to the RC even when capacity_addition[y_inv] = 0.

        With Primal Simplex (Method=0) the duals are exact LP duals — no approximation.

        Returns ``(result, result_operational)``, two lists of rc values in internal
        model units, one per row of df. ``result`` is the lifetime-dual reconstruction
        (above). ``result_operational`` replaces the lifetime-dual capacity value with
        the dispatch value from constraint_capacity_factor_conversion
        (sum_t max_load_t * dual - fixed_opex*discount), which excludes the reduced
        cost of the capacity variable that leaks into the lifetime dual when capacity
        is non-basic; it is degeneracy-immune for conversion techs and NaN otherwise.
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

        # Duals from diffusion constraints — capacity_addition[y_inv] appears in future
        # diffusion constraints for y > y_inv with coefficient -tdr[y]*kdr[y,y_inv]
        diff_total_series = None
        diff_an_series = None
        if "constraint_technology_diffusion_limit_total" in self.model.constraints:
            arr = self.model.constraints["constraint_technology_diffusion_limit_total"].dual
            if self.solver.use_scaling:
                labels = self.model.constraints["constraint_technology_diffusion_limit_total"].labels.data
                arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
            diff_total_series = arr.to_series().dropna()
        if "constraint_technology_diffusion_limit" in self.model.constraints:
            arr = self.model.constraints["constraint_technology_diffusion_limit"].dual
            if self.solver.use_scaling:
                labels = self.model.constraints["constraint_technology_diffusion_limit"].labels.data
                arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
            diff_an_series = arr.to_series().dropna()

        # Dual of the energy-to-power-ratio (min) constraint. Relevant only for the
        # storage-power perturbation (perturb_storage_power_addition_for_rc): there
        # capacity_addition[power] is held at its raised lower bound (non-basic) and
        # the constraint addition_energy - e2p_min*addition_power >= 0 binds. Its
        # dual carries the cost of the energy that is forced up alongside the power,
        # so it must enter the RC of the POWER component (coefficient -e2p_min on
        # capacity_addition[power], hence + e2p_min * dual in the RC, mirroring the
        # diffusion treatment below). index: (tech, node, year).
        e2p_min_dual_series = None
        e2p_min_param = getattr(params, "energy_to_power_ratio_min", None)
        cname_e2p = "constraint_capacity_energy_to_power_ratio_min"
        if cname_e2p in self.model.constraints:
            arr = self.model.constraints[cname_e2p].dual
            if self.solver.use_scaling:
                labels = self.model.constraints[cname_e2p].labels.data
                arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
            e2p_min_dual_series = arr.to_series().dropna()

        # ratio_MAX dual — only nonzero when a finite energy_to_power_ratio_max is
        # set (Path A: fixed ratio with ratio_min == ratio_max). Then the max
        # constraint can bind at near-viable storage nodes (energy capped at the
        # fixed duration); its dual must also enter the POWER reduced cost. Same
        # structure as ratio_min: capacity_addition[power] has coefficient -e2p_max.
        e2p_max_dual_series = None
        e2p_max_param = getattr(params, "energy_to_power_ratio_max", None)
        cname_e2p_max = "constraint_capacity_energy_to_power_ratio_max"
        if cname_e2p_max in self.model.constraints:
            arr = self.model.constraints[cname_e2p_max].dual
            if self.solver.use_scaling:
                labels = self.model.constraints[cname_e2p_max].labels.data
                arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
            e2p_max_dual_series = arr.to_series().dropna()

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

        # --- Operational valuation inputs (conversion only) -------------------
        # Degeneracy-immune alternative to the lifetime dual. By LP stationarity
        # of the reference-carrier flow, the dual of constraint_capacity_factor_
        # conversion (max_load*capacity - reference_flow >= 0) equals the per-hour
        # marginal operating value of one unit of capacity. Summed over a year
        # (weighted by max_load) and netted of fixed opex it gives the capacity's
        # net operating value WITHOUT the reduced cost of the capacity VARIABLE
        # that leaks into constraint_technology_lifetime's dual when capacity is
        # non-basic (unbuilt). opval_dispatch[(tech, node, year)] = sum_t
        # max_load_t * dual_capfactor_t. Only conversion techs have this clean
        # flow<=capacity mapping; storage/transport operational value needs the
        # storage-level/arbitrage duals and is left NaN.
        opval_dispatch = {}
        conv_techs = set()
        ofix_lookup = {}
        try:
            cf_name = "constraint_capacity_factor_conversion"
            if cf_name in self.model.constraints:
                arr = self.model.constraints[cf_name].dual
                if self.solver.use_scaling:
                    labels = self.model.constraints[cf_name].labels.data
                    arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
                cf = arr.to_series().dropna().rename("dual").reset_index()

                def _pick(columns, kind):
                    for n in columns:
                        if not isinstance(n, str):
                            continue
                        low = n.lower()
                        if kind == "time" and "time" in low and "oper" in low:
                            return n
                        if kind == "tech" and "technolog" in low:
                            return n
                        if kind == "node" and ("node" in low or "location" in low):
                            return n
                    return None

                cf_cols = list(cf.columns)
                c_t = _pick(cf_cols, "time")
                c_tech = _pick(cf_cols, "tech")
                c_node = _pick(cf_cols, "node")
                cf["__y"] = cf[c_t].map(
                    lambda t: int(es.time_steps.convert_time_step_operation2year(t))
                )
                ml = params.max_load.to_series().dropna().rename("m").reset_index()
                ml_cols = list(ml.columns)
                m_t = _pick(ml_cols, "time")
                m_tech = _pick(ml_cols, "tech")
                m_node = _pick(ml_cols, "node")
                merged = cf.merge(ml, left_on=[c_tech, c_node, c_t],
                                  right_on=[m_tech, m_node, m_t], how="left")
                merged["m"] = merged["m"].fillna(1.0)
                merged["__mdual"] = merged["m"] * merged["dual"]
                g = merged.groupby([c_tech, c_node, "__y"])["__mdual"].sum()
                opval_dispatch = {(str(t), str(n), int(y)): float(v)
                                  for (t, n, y), v in g.items()}
                conv_techs = set(k[0] for k in opval_dispatch)
            ofs = getattr(params, "opex_specific_fixed", None)
            if ofs is not None:
                for idx2, val2 in ofs.to_series().dropna().items():
                    if not isinstance(idx2, tuple):
                        idx2 = (idx2,)
                    if len(idx2) == 4:        # (tech, ctype, location, year)
                        ofix_lookup[(idx2[0], idx2[1], idx2[2], idx2[3])] = float(val2)
                    elif len(idx2) == 3:      # (tech, location, year)
                        ofix_lookup[(idx2[0], None, idx2[1], idx2[2])] = float(val2)
        except Exception as e:
            logging.debug(f"Operational RC precompute failed: {e}")
            opval_dispatch, conv_techs, ofix_lookup = {}, set(), {}

        tech_cache = {}
        diff_param_cache = {}  # tech -> (kdr_rate, spillover_rate)
        result = []
        result_operational = []

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
                    result_operational.append(np.nan)
                    continue

                cs = capex_lookup.get((tech, ctype, node, y_inv),
                     capex_lookup.get((tech, node, y_inv), np.nan))
                if np.isnan(cs):
                    result.append(np.nan)
                    result_operational.append(np.nan)
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
                    if not matches.empty:
                        elec_value += -float(matches.iloc[0])
                    # else: dual is NaN (LP degenerate when diffusion constraint is
                    # binding — the lifetime constraint is not the active bound).
                    # Treat as 0; the value is captured by diff_contribution below.

                # Diffusion dual contribution: capacity_addition[y_inv] appears in future
                # diffusion constraints (y > y_inv) with coefficient -tdr[y]*kdr[y,y_inv].
                # The RC contribution from constraint y is: mu_diff[y] * tdr[y] * kdr[y,y_inv].
                # (mu_diff <= 0 for binding <= constraints; tdr,kdr > 0 => contribution < 0,
                #  i.e. building now relaxes future diffusion limits and lowers the RC.)
                
                diff_contribution = 0.0
                future_years = [y for y in years if y > y_inv]
                if future_years and (diff_total_series is not None or diff_an_series is not None):
                    if tech not in diff_param_cache:
                        try:
                            kdr_rate = float(np.squeeze(
                                params.knowledge_depreciation_rate.sel(
                                    set_technologies=tech).values))
                        except Exception:
                            kdr_rate = 0.0
                        try:
                            sr = float(np.squeeze(
                                params.knowledge_spillover_rate.sel(
                                    set_technologies=tech).values))
                        except Exception:
                            sr = np.inf
                        diff_param_cache[tech] = (kdr_rate, sr)
                    kdr_rate, sr = diff_param_cache[tech]

                    for y_fut in future_years:
                        # kdr: knowledge decay from y_inv to y_fut
                        # exponent = interval * (y_fut - 1 - y_inv) matching technology.py
                        kdr_val = (1.0 - kdr_rate) ** (dy * (y_fut - 1 - y_inv))

                        try:
                            mdr_fut = float(np.squeeze(
                                params.max_diffusion_rate.sel(
                                    set_technologies=tech,
                                    set_time_steps_yearly=y_fut).values))
                        except Exception:
                            continue
                        tdr_fut = (1.0 + mdr_fut) ** dy - 1.0
                        if tdr_fut <= 0:
                            continue

                        coeff = tdr_fut * kdr_val

                        # constraint_technology_diffusion_limit_total is summed over all nodes
                        # → index is (tech, ctype, year), no node dimension
                        if diff_total_series is not None:
                            mask = (
                                (diff_total_series.index.get_level_values(0) == tech)
                                & (diff_total_series.index.get_level_values(1) == ctype)
                                & (diff_total_series.index.get_level_values(2) == y_fut)
                            )
                            if mask.any():
                                diff_contribution += float(diff_total_series[mask].iloc[0]) * coeff

                        # constraint_technology_diffusion_limit (with spillover)
                        if diff_an_series is not None and not np.isinf(sr):
                            # same-node contribution (coefficient = tdr * 1 * kdr)
                            mask_sn = (
                                (diff_an_series.index.get_level_values(0) == tech)
                                & (diff_an_series.index.get_level_values(1) == ctype)
                                & (diff_an_series.index.get_level_values(2) == node)
                                & (diff_an_series.index.get_level_values(3) == y_fut)
                            )
                            if mask_sn.any():
                                diff_contribution += float(diff_an_series[mask_sn].iloc[0]) * coeff

                            # cross-node contribution (coefficient = tdr * sr * kdr)
                            for other_node in diff_an_series.index.get_level_values(2).unique():
                                if other_node == node:
                                    continue
                                mask_cn = (
                                    (diff_an_series.index.get_level_values(0) == tech)
                                    & (diff_an_series.index.get_level_values(1) == ctype)
                                    & (diff_an_series.index.get_level_values(2) == other_node)
                                    & (diff_an_series.index.get_level_values(3) == y_fut)
                                )
                                if mask_cn.any():
                                    diff_contribution += (
                                        float(diff_an_series[mask_cn].iloc[0]) * tdr_fut * sr * kdr_val
                                    )

                # Energy-to-power-ratio (min) dual contribution — POWER component of
                # storage only. capacity_addition[power] has coefficient -e2p_min in
                # the constraint, so its RC contribution is + e2p_min * dual (added,
                # like diff_contribution). 0 for everything else (constraint absent,
                # non-storage, energy component, or e2p_min unset/<=0).
                e2p_contribution = 0.0
                for _dual_series, _param in (
                    (e2p_min_dual_series, e2p_min_param),
                    (e2p_max_dual_series, e2p_max_param),
                ):
                    if (_dual_series is None or ctype != "power" or _param is None):
                        continue
                    try:
                        e2p_val = float(np.squeeze(
                            _param.sel(set_storage_technologies=tech).values))
                    except Exception:
                        e2p_val = 0.0
                    if np.isfinite(e2p_val) and e2p_val > 0:
                        mask = (
                            (_dual_series.index.get_level_values(0) == tech)
                            & (_dual_series.index.get_level_values(-2) == node)
                            & (_dual_series.index.get_level_values(-1) == y_inv)
                        )
                        if mask.any():
                            e2p_contribution += (
                                float(_dual_series[mask].iloc[0]) * e2p_val
                            )

                result.append(
                    np.nan if np.isnan(elec_value)
                    else cs - (elec_value - diff_contribution - e2p_contribution) / scaling
                )

                # Operational reduced cost (conversion only): same formula, but the
                # capacity value is taken from the dispatch dual (sum_t max_load*
                # capacity_factor_dual) minus fixed opex, instead of from the
                # lifetime dual. This excludes the reduced cost of the capacity
                # variable that leaks into the lifetime dual when capacity is
                # non-basic, so it stays interpretable for unbuilt techs. NaN for
                # non-conversion (storage/transport).
                if tech in conv_techs:
                    elec_value_op = 0.0
                    for y in pay_years:
                        elec_value_op += opval_dispatch.get((tech, node, y), 0.0)
                        ofx = ofix_lookup.get((tech, ctype, node, y),
                              ofix_lookup.get((tech, None, node, y), 0.0))
                        elec_value_op -= ofx * discount_factors[y]
                    result_operational.append(
                        cs - (elec_value_op - diff_contribution - e2p_contribution) / scaling
                    )
                else:
                    result_operational.append(np.nan)

            except Exception:
                result.append(np.nan)
                result_operational.append(np.nan)

        return result, result_operational

    def save_capacity_addition_analysis(self):
        """Saves capacity_addition values and capex-equivalent reduced costs to CSV.

        Output: <output_dir>/capacity_addition_analysis.csv

        Columns:
          unit                             base unit of capacity_addition
          value                            optimal capacity addition [GW]
          capacity                         total installed capacity = existing +
                                           additions [GW]; shows the phantom
                                           +delta at perturbed greenfield nodes
          capacity_ceiling                 binding upper limit on capacity =
                                           min(variable upper bound, capacity_limit)
                                           [GW]; inf = unbounded
          vbasis                           Gurobi basis status (reliability flag):
                                           0 = basic (degenerate -> rc unreliable),
                                           -1/-2 = nonbasic, -3 = superbasic
          rc_capex_equivalent              dual-based RC [model units]
          rc_capex_equivalent_input_units  dual-based RC [Euro/kW installed]

        rc_capex_equivalent_input_units answers:
          "By how much must capex decrease for this technology to become optimal?"
          = 0 for built technologies, > 0 for unbuilt technologies.

        The per-year dual breakdown behind rc_capex_equivalent is written to
        rc_components.csv by save_rc_components().

        Requires Primal Simplex (Method=0) for exact duals. See main_rc.py.
        The +eps perturbation (solver_options["rc_perturbation"]) selects the
        economically correct dual endpoint at unbuilt technologies; it enters
        rc_capex_equivalent only through the basis, not as an explicit term.
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

        # Gurobi basis status (VBasis attribute) — reliability flag for rc_capex:
        #    0 = basic, -1 = nonbasic@lower, -2 = nonbasic@upper, -3 = superbasic
        # A row with value ~ 0 AND vbasis == 0 is a *degenerate basic variable*:
        # basic variables have reduced cost 0 by definition, which mechanically
        # forces rc_capex_equivalent to 0 regardless of the true economic distance.
        # Such a 0 must NOT be read as "marginally profitable".
        # Requires Crossover=1 (without crossover no basis exists -> all NaN).
        if self.solver.name == "gurobi":
            try:
                vbasis_arr = self.model.variables["capacity_addition"].get_solver_attribute("VBasis")
                df["vbasis"] = vbasis_arr.to_series()
            except Exception as e:
                logging.debug(f"Could not retrieve Gurobi VBasis: {e}")
                df["vbasis"] = np.nan
        else:
            df["vbasis"] = np.nan

        # Total installed capacity (= existing + additions) and the capacity
        # variable's upper bound, for sanity-checking the RC cases (greenfield
        # vs brownfield, whether a technology sits at its ceiling, and the
        # phantom +delta from the lifetime-RHS perturbation showing up as a tiny
        # capacity at perturbed greenfield nodes). Model units (= input units
        # when use_scaling=0, as in the RC analysis); inf = no upper bound.
        try:
            df["capacity"] = self.model.solution["capacity"].to_series().reindex(df.index)
        except Exception as e:
            logging.debug(f"Could not retrieve capacity: {e}")
            df["capacity"] = np.nan
        try:
            cap_upper = self.model.variables["capacity"].upper.to_series().reindex(df.index)
            cap_limit = self.params.capacity_limit.to_series().reindex(df.index)
            # effective ceiling on capacity = min(variable upper bound, which folds
            # in capacity_addition_max, and the capacity_limit constraint). This is
            # the binding upper limit the lifetime-RHS perturbation guard uses;
            # inf = unbounded.
            df["capacity_ceiling"] = np.minimum(
                cap_upper.fillna(np.inf), cap_limit.fillna(np.inf)
            )
        except Exception as e:
            logging.debug(f"Could not retrieve capacity ceiling: {e}")
            df["capacity_ceiling"] = np.nan

        # Dual-based capex-equivalent RC — primary reliable metric.
        # rc_capex_equivalent           : reconstruction from the lifetime dual (legacy)
        # rc_capex_equivalent_operational: reconstruction from the operational
        #   (capacity-factor) dual, which excludes the leaked reduced cost of the
        #   capacity variable (degeneracy-immune; conversion only, else NaN).
        try:
            rc_life, rc_op = self._compute_rc_capex_equivalent(df)
            df["rc_capex_equivalent"] = rc_life
            df["rc_capex_equivalent_operational"] = rc_op
        except Exception as e:
            logging.warning(f"Could not compute rc_capex_equivalent: {e}")
            df["rc_capex_equivalent"] = np.nan
            df["rc_capex_equivalent_operational"] = np.nan

        # Convert to input units (Euro/kW): invert the fraction_year scaling.
        # ZEN-garden stores capex_specific internally as input_value * fraction_year,
        # so dividing by fraction_year recovers the original Euro/kW unit.
        # NOTE: fraction_year == 1 whenever the model is not time-aggregated for
        # capex (unaggregated_time_steps_per_year == total_hours_per_year); then
        # this column equals rc_capex_equivalent.
        try:
            fraction_year = (
                self.system.unaggregated_time_steps_per_year
                / self.system.total_hours_per_year
            )
            df["rc_capex_equivalent_input_units"] = df["rc_capex_equivalent"] / fraction_year
            df["rc_capex_equivalent_operational_input_units"] = (
                df["rc_capex_equivalent_operational"] / fraction_year
            )
        except Exception as e:
            logging.warning(f"Could not compute rc_capex_equivalent_input_units: {e}")
            df["rc_capex_equivalent_input_units"] = np.nan
            df["rc_capex_equivalent_operational_input_units"] = np.nan

        df = df[["unit", "value", "capacity", "capacity_ceiling", "vbasis",
                 "rc_capex_equivalent", "rc_capex_equivalent_input_units",
                 "rc_capex_equivalent_operational",
                 "rc_capex_equivalent_operational_input_units"]]

        csv_file = self.name_dir.joinpath("capacity_addition_analysis.csv")
        df.to_csv(csv_file)
        logging.info(f"Capacity addition analysis saved to {csv_file}")

        self.save_rc_components()

        # Per-technology-type, classified, visualization-ready split of the analysis
        # (conversion / transport / storage). Best-effort: a failure here must not
        # break the main analysis output above.
        try:
            self.save_capacity_addition_classified(df)
        except Exception as e:
            logging.warning(f"Could not save classified capacity addition analysis: {e}")

        # Optional: render the RC heatmaps for this scenario folder. Opt-in via
        # config analysis.generate_rc_heatmaps. Best-effort.
        if getattr(self.analysis, "generate_rc_heatmaps", False):
            try:
                self._generate_rc_heatmaps()
            except Exception as e:
                logging.warning(f"Could not generate RC heatmaps: {e}")

        # Diagnostic: full per-constraint reduced-cost decomposition of capacity_addition
        # for configured targets (analysis.rc_dual_dump). Best-effort.
        if getattr(self.analysis, "rc_dual_dump", False):
            try:
                self.dump_rc_decomposition()
            except Exception as e:
                logging.warning(f"Could not dump RC decomposition: {e}")

    def save_rc_components(self):
        """Saves the per-year dual contributions to the RC to rc_components.csv.

        One row per (tech, ctype, node, y_inv, constraint_type, component_year).

        Columns
        -------
        set_technologies, set_capacity_types, set_location, set_time_steps_yearly
            Investment dimensions — match the index of capacity_addition_analysis.csv.
        constraint_type
            'lifetime'        — constraint_technology_lifetime
            'diffusion_total' — constraint_technology_diffusion_limit_total (summed over nodes)
            'diffusion_an'    — constraint_technology_diffusion_limit (per-node, only if spillover finite)
        component_year
            The year index of the contributing constraint row.
        raw_dual
            Dual value from linopy in model units (scaled if use_scaling=True).
        coefficient
            Coefficient of capacity_addition[y_inv] in this constraint row.
            1.0 for lifetime;  tdr * kdr  for diffusion.
        discount_factor
            δ(component_year) — only meaningful for lifetime rows (nan for diffusion).
        scaling
            af * Σ_y δ(y)  over the technology's pay_years — same for all rows of a
            given (tech, y_inv) combination.
        contribution_to_rc
            raw_dual * coefficient / scaling.
            Summing over all rows with the same (tech, ctype, node, y_inv) and adding
            capex_specific reproduces rc_capex_equivalent from capacity_addition_analysis.csv.
        """
        if "capacity_addition" not in self.model.variables:
            return
        if "constraint_technology_lifetime" not in self.model.constraints:
            return

        var_values = self.model.solution["capacity_addition"]
        df_main = var_values.to_series().dropna().to_frame("value")
        if df_main.empty:
            return

        params = self.optimization_setup.parameters
        system = self.optimization_setup.system
        es = self.optimization_setup.energy_system

        r = float(params.discount_rate)
        dy = system.interval_between_years
        years = list(es.set_time_steps_yearly)
        first_year = years[0]
        last_year_entire = es.set_time_steps_yearly_entire_horizon[-1]

        discount_factors = {}
        for y in years:
            iv = 1 if y == last_year_entire else dy
            discount_factors[y] = sum(
                (1.0 / (1.0 + r)) ** (dy * (y - first_year) + i)
                for i in range(iv)
            )

        # Lifetime duals
        dual_arr = self.model.constraints["constraint_technology_lifetime"].dual
        if self.solver.use_scaling:
            cons_labels = self.model.constraints["constraint_technology_lifetime"].labels.data
            dual_arr = dual_arr * self.optimization_setup.scaling.D_r_inv[cons_labels]
        dual_series = dual_arr.to_series().dropna()

        # Diffusion duals (same logic as _compute_rc_capex_equivalent)
        diff_total_series = None
        diff_an_series = None
        if "constraint_technology_diffusion_limit_total" in self.model.constraints:
            arr = self.model.constraints["constraint_technology_diffusion_limit_total"].dual
            if self.solver.use_scaling:
                labels = self.model.constraints["constraint_technology_diffusion_limit_total"].labels.data
                arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
            diff_total_series = arr.to_series().dropna()
        if "constraint_technology_diffusion_limit" in self.model.constraints:
            arr = self.model.constraints["constraint_technology_diffusion_limit"].dual
            if self.solver.use_scaling:
                labels = self.model.constraints["constraint_technology_diffusion_limit"].labels.data
                arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
            diff_an_series = arr.to_series().dropna()

        # Energy-to-power-ratio (min) dual — POWER component of storage only
        # (see _compute_rc_capex_equivalent). index: (tech, node, year).
        e2p_dual_series = {}   # ratio_type -> (param, dual_series)
        for ratio_type in ("min", "max"):
            param = getattr(params, f"energy_to_power_ratio_{ratio_type}", None)
            cname = f"constraint_capacity_energy_to_power_ratio_{ratio_type}"
            if param is None or cname not in self.model.constraints:
                continue
            arr = self.model.constraints[cname].dual
            if self.solver.use_scaling:
                labels = self.model.constraints[cname].labels.data
                arr = arr * self.optimization_setup.scaling.D_r_inv[labels]
            e2p_dual_series[ratio_type] = (param, arr.to_series().dropna())

        rows = []
        tech_cache = {}
        diff_param_cache = {}

        for idx in df_main.index:
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
                    continue

                base = {
                    "set_technologies":     tech,
                    "set_capacity_types":   ctype,
                    "set_location":         node,
                    "set_time_steps_yearly": y_inv,
                    "scaling":              scaling,
                }

                # ── Lifetime contributions ──────────────────────────────────
                for y in pay_years:
                    mask = (
                        (dual_series.index.get_level_values(0) == tech)
                        & (dual_series.index.get_level_values(1) == ctype)
                        & (dual_series.index.get_level_values(2) == node)
                        & (dual_series.index.get_level_values(3) == y)
                    )
                    raw_dual = float(dual_series[mask].iloc[0]) if mask.any() else np.nan
                    rows.append({
                        **base,
                        "constraint_type":   "lifetime",
                        "component_year":    y,
                        "raw_dual":          raw_dual,
                        "coefficient":       1.0,
                        "discount_factor":   discount_factors[y],
                        "contribution_to_rc": raw_dual / scaling if not np.isnan(raw_dual) else np.nan,
                    })

                # ── Diffusion contributions ─────────────────────────────────
                future_years = [y for y in years if y > y_inv]
                if future_years and (diff_total_series is not None or diff_an_series is not None):
                    if tech not in diff_param_cache:
                        try:
                            kdr_rate = float(np.squeeze(
                                params.knowledge_depreciation_rate.sel(
                                    set_technologies=tech).values))
                        except Exception:
                            kdr_rate = 0.0
                        try:
                            sr = float(np.squeeze(
                                params.knowledge_spillover_rate.sel(
                                    set_technologies=tech).values))
                        except Exception:
                            sr = np.inf
                        diff_param_cache[tech] = (kdr_rate, sr)
                    kdr_rate, sr = diff_param_cache[tech]

                    for y_fut in future_years:
                        kdr_val = (1.0 - kdr_rate) ** (dy * (y_fut - 1 - y_inv))
                        try:
                            mdr_fut = float(np.squeeze(
                                params.max_diffusion_rate.sel(
                                    set_technologies=tech,
                                    set_time_steps_yearly=y_fut).values))
                        except Exception:
                            continue
                        tdr_fut = (1.0 + mdr_fut) ** dy - 1.0
                        if tdr_fut <= 0:
                            continue
                        coeff = tdr_fut * kdr_val

                        # constraint_technology_diffusion_limit_total — index (tech, ctype, year)
                        if diff_total_series is not None:
                            mask = (
                                (diff_total_series.index.get_level_values(0) == tech)
                                & (diff_total_series.index.get_level_values(1) == ctype)
                                & (diff_total_series.index.get_level_values(2) == y_fut)
                            )
                            if mask.any():
                                raw_dual = float(diff_total_series[mask].iloc[0])
                                rows.append({
                                    **base,
                                    "constraint_type":    "diffusion_total",
                                    "component_year":     y_fut,
                                    "raw_dual":           raw_dual,
                                    "coefficient":        coeff,
                                    "discount_factor":    np.nan,
                                    "contribution_to_rc": raw_dual * coeff / scaling,
                                })

                        # constraint_technology_diffusion_limit — index (tech, ctype, node, year)
                        if diff_an_series is not None and not np.isinf(sr):
                            mask_sn = (
                                (diff_an_series.index.get_level_values(0) == tech)
                                & (diff_an_series.index.get_level_values(1) == ctype)
                                & (diff_an_series.index.get_level_values(2) == node)
                                & (diff_an_series.index.get_level_values(3) == y_fut)
                            )
                            if mask_sn.any():
                                raw_dual = float(diff_an_series[mask_sn].iloc[0])
                                rows.append({
                                    **base,
                                    "constraint_type":    "diffusion_an",
                                    "component_year":     y_fut,
                                    "raw_dual":           raw_dual,
                                    "coefficient":        coeff,
                                    "discount_factor":    np.nan,
                                    "contribution_to_rc": raw_dual * coeff / scaling,
                                })

                # ── Energy-to-power-ratio (min/max) contributions ───────────
                # POWER component of storage only; coefficient = e2p_ratio (the
                # forced energy per unit power). Reproduces the e2p term added in
                # _compute_rc_capex_equivalent. ratio_max only contributes when a
                # finite ratio_max is set (Path A: fixed ratio).
                if ctype == "power":
                    for ratio_type, (param, e2p_ds) in e2p_dual_series.items():
                        try:
                            e2p_val = float(np.squeeze(
                                param.sel(set_storage_technologies=tech).values))
                        except Exception:
                            e2p_val = 0.0
                        if not (np.isfinite(e2p_val) and e2p_val > 0):
                            continue
                        mask = (
                            (e2p_ds.index.get_level_values(0) == tech)
                            & (e2p_ds.index.get_level_values(-2) == node)
                            & (e2p_ds.index.get_level_values(-1) == y_inv)
                        )
                        if mask.any():
                            raw_dual = float(e2p_ds[mask].iloc[0])
                            rows.append({
                                **base,
                                "constraint_type":    f"e2p_ratio_{ratio_type}",
                                "component_year":     y_inv,
                                "raw_dual":           raw_dual,
                                "coefficient":        e2p_val,
                                "discount_factor":    np.nan,
                                "contribution_to_rc": raw_dual * e2p_val / scaling,
                            })

            except Exception:
                continue

        if not rows:
            logging.info("No RC components to save — rc_components.csv not written")
            return

        out_df = pd.DataFrame(rows)
        csv_file = self.name_dir.joinpath("rc_components.csv")
        out_df.to_csv(csv_file, index=False)
        logging.info(f"RC components saved to {csv_file} ({len(rows)} rows)")

    # ---------------------------------------------------------------------------
    # Classified, per-technology-type RC analysis (visualization-ready)
    # ---------------------------------------------------------------------------

    def _capex_specific_lookup(self):
        """Returns {(tech, ctype, node, year) -> capex} and {(tech, node, year) -> capex}.

        Source: the capex_specific_{conversion,storage,transport} parameters — the
        specific capex the model uses for the planning year (= the value in the capex
        input CSVs, multiplied by fraction_year). This is exactly the term the reduced
        cost is measured against: rc_capex_equivalent = capex_specific - operating_value.
        Divide by fraction_year to recover Euro/kW (see save_capacity_addition_analysis).

        For storage the parameter carries BOTH the power and the energy component via
        the set_capacity_types dimension, so the (tech, ctype, ...) key resolves the
        energy capex for ctype='energy' and the power capex for ctype='power'.
        """
        params = self.optimization_setup.parameters
        lookup = {}
        for param_name in ("capex_specific_conversion", "capex_specific_storage",
                           "capex_specific_transport"):
            p = getattr(params, param_name, None)
            if p is None:
                continue
            try:
                for idx, val in p.to_series().dropna().items():
                    if not isinstance(idx, tuple):
                        idx = (idx,)
                    tech_name, year_val, node_val = idx[0], idx[-1], idx[-2]
                    ctype_val = idx[1] if len(idx) == 4 else None
                    lookup.setdefault((tech_name, node_val, year_val), float(val))
                    lookup.setdefault((tech_name, ctype_val, node_val, year_val), float(val))
            except Exception:
                continue
        return lookup

    def save_capacity_addition_classified(self, df):
        """Writes per-technology-type, classified RC analyses for visualization.

        Splits capacity_addition_analysis into three CSVs by technology class and adds,
        per row, the *case* and the original specific capex from the capex input files
        [Euro/kW] (the value the RC is subtracted from), so one can answer "where are
        unbuilt technologies actually close?".

        Cases (see docs/capacity_addition_analysis.md §3/§6):
          built                 value > 0 — already deployed, rc ~ 0
          buildable_rc          value ~ 0, head-room left, rc > 0  -> honest distance ✅
          at_limit              value ~ 0, capacity ~ ceiling  -> no expansion possible
          not_buildable         value ~ 0, ceiling ~ 0  -> blocked/forbidden, ignore rc
          blocked_profitable    value ~ 0, rc < 0  -> blocked but profitable (separate topic)
          breakeven_unreliable  value ~ 0, head-room, rc ~ 0  -> degenerate, rc not reliable

        Conversion/transport (single 'power' component): the extra columns are
          capex_specific_input_units  original capex [Euro/kW]
          ratio_reduction             rc / capex  = fraction the capex must drop to build
                                      (only for case in {built, buildable_rc})

        Storage uses a DEDICATED structure (one row per tech/node/year, carried by the
        POWER row; see docs/rc_storage_power_energy.md). The reduced cost read from the
        power row is the *bundle* distance C_bundle - V_bundle, with
        C_bundle = capex_power + D * capex_energy  (D = energy_to_power_ratio [h]).
        Closing the gap by subtracting the SAME absolute value Δ from both capex needs
            Δ_P + D * Δ_E = rc_power ,  Δ_P = Δ_E = Δ  =>  Δ = rc_power / (1 + D).
        Reported columns:
          rc_mathematical                the bundle RC from the power row [Euro/kW]
          e2p                            D, the duration factor [h]
          capex_power / capex_energy     original capex [Euro/kW] / [Euro/kWh]
          C_bundle                       capex_power + e2p * capex_energy [Euro/kW]
          RC_power / RC_energy           Δ (same absolute reduction on both)
          ratio_power_reduction          Δ / capex_power  (differs from ...)
          ratio_energy_reduction         Δ / capex_energy
          ratio_reduction_proportional   f = rc_power / C_bundle  (both capex cut same %)

        Outputs (next to capacity_addition_analysis.csv):
          capacity_addition_analysis_conversion.csv
          capacity_addition_analysis_transport.csv
          capacity_addition_analysis_storage.csv
        """
        # ── tolerances ──────────────────────────────────────────────────────
        CEIL_ZERO = 1e-6     # ceiling ~ 0  -> nothing can be built
        CEIL_REL  = 1e-4     # |capacity - ceiling| (relative) -> sitting at the limit
        RC_ZERO   = 1e-6     # |rc| ~ 0
        VALUE_TOL = 1e-6     # value > tol -> built (non-storage)
        # storage power probe sits at the raised floor (yotta); read it from the
        # solver options if still present, else default. Real builds are >> yotta.
        yotta = 1e-4
        try:
            so = getattr(self.solver, "solver_options", {}) or {}
            yv = so.get("rc_storage_power_perturbation")
            if yv:
                yotta = float(yv)
        except Exception:
            pass
        STORAGE_BUILT_TOL = max(5.0 * yotta, VALUE_TOL)
        # Multi-year carry-over: a storage built in a PRIOR year persists via its
        # lifetime. In later years value_power is just the forced yotta-probe while
        # capacity already carries the prior build -> capacity - value >> 0. Probing
        # an already-built storage yields a phantom rc (often ratio > 100 %). Detect
        # via this threshold (well above the perturbation artifacts yotta/e2p*yotta,
        # below any real build).
        CARRY_TOL = 1e-2

        params = self.optimization_setup.parameters
        sets = self.optimization_setup.sets

        try:
            fraction_year = (self.system.unaggregated_time_steps_per_year
                             / self.system.total_hours_per_year)
        except Exception:
            fraction_year = 1.0

        # tech -> technology class. Retrofitting technologies (e.g. *_CCS) are a
        # conversion subclass with a single 'power' component, so they are folded
        # into 'conversion' (mapped last so they win over a generic membership).
        type_of_tech = {}
        for sname, tname in (("set_conversion_technologies", "conversion"),
                             ("set_transport_technologies", "transport"),
                             ("set_storage_technologies", "storage"),
                             ("set_retrofitting_technologies", "conversion")):
            try:
                for t in sets[sname]:
                    type_of_tech[str(t)] = tname
            except Exception:
                continue

        # storage tech -> D (energy_to_power_ratio); no-probe/placeholder techs -> nan
        e2p_of_tech = {}
        e2p_param = getattr(params, "energy_to_power_ratio_min", None)
        try:
            storage_techs = list(sets["set_storage_technologies"])
        except Exception:
            storage_techs = []
        for t in storage_techs:
            v = np.nan
            if e2p_param is not None:
                try:
                    v = float(np.squeeze(e2p_param.sel(set_storage_technologies=t).values))
                except Exception:
                    v = np.nan
            e2p_of_tech[str(t)] = v if (np.isfinite(v) and v > 0) else np.nan

        capex_lookup = self._capex_specific_lookup()

        work = df.reset_index()
        idx_cols = list(work.columns)[:4]
        tcol, ccol, ncol, ycol = idx_cols

        def capex_input(tech, ctype, node, year):
            cs = capex_lookup.get((tech, ctype, node, year),
                 capex_lookup.get((tech, node, year), np.nan))
            return (cs / fraction_year) if (cs is not None and np.isfinite(cs)) else np.nan

        work["tech_type"] = work[tcol].map(lambda t: type_of_tech.get(str(t), "unknown"))
        work["capex_specific_input_units"] = [
            capex_input(r[tcol], r[ccol], r[ncol], r[ycol])
            for _, r in work.iterrows()
        ]

        def classify(value, capacity, ceiling, rc, built_tol):
            v = value if np.isfinite(value) else 0.0
            cap = capacity if np.isfinite(capacity) else 0.0
            rcv = rc if np.isfinite(rc) else 0.0
            inf_ceiling = not np.isfinite(ceiling)
            if v > built_tol:
                return "built"
            if (not inf_ceiling) and ceiling <= CEIL_ZERO:
                return "not_buildable"
            if (not inf_ceiling) and cap > CEIL_ZERO \
                    and abs(cap - ceiling) <= CEIL_REL * max(1.0, abs(ceiling)):
                return "at_limit"
            if rcv > RC_ZERO:
                return "buildable_rc"
            if rcv < -RC_ZERO:
                return "blocked_profitable"
            return "breakeven_unreliable"

        # ── non-storage: conversion & transport ─────────────────────────────
        ns = work[work["tech_type"].isin(["conversion", "transport"])].copy()
        if not ns.empty:
            ns["case"] = [
                classify(r["value"], r["capacity"], r["capacity_ceiling"],
                         r["rc_capex_equivalent_input_units"], VALUE_TOL)
                for _, r in ns.iterrows()
            ]

            def ns_ratio(r):
                cs = r["capex_specific_input_units"]
                if r["case"] in ("built", "buildable_rc") and np.isfinite(cs) and cs > CEIL_ZERO:
                    return r["rc_capex_equivalent_input_units"] / cs
                return np.nan

            ns["ratio_reduction"] = [ns_ratio(r) for _, r in ns.iterrows()]
            ns["rc_reliable"] = ns["case"].isin(["built", "buildable_rc"])

            # Operational (degeneracy-immune) reduced cost, passed through from
            # capacity_addition_analysis.csv, plus its own ratio = rc_op / capex.
            # NaN for transport (only conversion has the operational reconstruction).
            def ns_ratio_op(r):
                cs = r["capex_specific_input_units"]
                rcop = r.get("rc_capex_equivalent_operational_input_units", np.nan)
                if (r["case"] in ("built", "buildable_rc") and np.isfinite(cs)
                        and cs > CEIL_ZERO and np.isfinite(rcop)):
                    return rcop / cs
                return np.nan

            if "rc_capex_equivalent_operational" not in ns.columns:
                ns["rc_capex_equivalent_operational"] = np.nan
                ns["rc_capex_equivalent_operational_input_units"] = np.nan
            ns["ratio_reduction_operational"] = [ns_ratio_op(r) for _, r in ns.iterrows()]

            out_cols = [tcol, ccol, ncol, ycol, "tech_type", "unit", "value",
                        "capacity", "capacity_ceiling", "vbasis", "case",
                        "capex_specific_input_units", "rc_capex_equivalent",
                        "rc_capex_equivalent_input_units", "ratio_reduction",
                        "rc_capex_equivalent_operational",
                        "rc_capex_equivalent_operational_input_units",
                        "ratio_reduction_operational", "rc_reliable"]
            for tname in ("conversion", "transport"):
                sub = ns[ns["tech_type"] == tname]
                if sub.empty:
                    continue
                fpath = self.name_dir.joinpath(f"capacity_addition_analysis_{tname}.csv")
                sub[out_cols].to_csv(fpath, index=False)
                logging.info(f"Classified {tname} RC analysis saved to {fpath} "
                             f"({len(sub)} rows)")

        # ── storage: bundle structure (one row per tech/node/year) ──────────
        st = work[work["tech_type"] == "storage"].copy()
        if not st.empty:
            pw = st[st[ccol] == "power"].set_index([tcol, ncol, ycol])
            en = st[st[ccol] == "energy"].set_index([tcol, ncol, ycol])
            rows = []
            for key in pw.index.union(en.index):
                tech = key[0]
                p = pw.loc[key] if key in pw.index else None
                e = en.loc[key] if key in en.index else None
                D = e2p_of_tech.get(str(tech), np.nan)

                v_p = float(p["value"]) if p is not None else np.nan
                cap_p = float(p["capacity"]) if p is not None else np.nan
                ceil_p = float(p["capacity_ceiling"]) if p is not None else np.nan
                rc_p = float(p["rc_capex_equivalent_input_units"]) if p is not None else np.nan
                cx_p = float(p["capex_specific_input_units"]) if p is not None else np.nan
                cx_e = float(e["capex_specific_input_units"]) if e is not None else np.nan

                case = (classify(v_p, cap_p, ceil_p, rc_p, STORAGE_BUILT_TOL)
                        if p is not None else "no_power_row")

                # Multi-year carry-over: capacity carried from a prior year's build
                # (capacity - value beyond the probe) means the storage is already
                # built here. The forced yotta-probe then produces a phantom rc on an
                # already-built storage -> treat as built and drop the meaningless rc.
                carried_over = (p is not None and np.isfinite(cap_p) and np.isfinite(v_p)
                                and (cap_p - v_p) > CARRY_TOL)
                if carried_over and case == "buildable_rc":
                    case = "built"
                    rc_p = np.nan  # probe phantom on an already-built storage

                # bundle decomposition — same absolute value Δ subtracted from both
                C_bundle = (cx_p + D * cx_e) if (np.isfinite(D) and np.isfinite(cx_p)
                                                 and np.isfinite(cx_e)) else np.nan
                delta = (rc_p / (1.0 + D)) if (np.isfinite(D) and np.isfinite(rc_p)) else np.nan
                ratio_p = (delta / cx_p) if (np.isfinite(delta) and np.isfinite(cx_p)
                                             and cx_p > CEIL_ZERO) else np.nan
                ratio_e = (delta / cx_e) if (np.isfinite(delta) and np.isfinite(cx_e)
                                             and cx_e > CEIL_ZERO) else np.nan
                f_prop = (rc_p / C_bundle) if (np.isfinite(rc_p) and np.isfinite(C_bundle)
                                               and C_bundle > CEIL_ZERO) else np.nan

                placeholder = (str(tech) in ("oil_storage", "natural_gas_storage")) \
                    or (not np.isfinite(D))
                rc_reliable = (case in ("built", "buildable_rc")) and (not placeholder)
                # decomposition is only meaningful for actionable cases
                if case not in ("built", "buildable_rc"):
                    delta = ratio_p = ratio_e = f_prop = np.nan

                rows.append({
                    tcol: tech, ncol: key[1], ycol: key[2],
                    "tech_type": "storage",
                    "unit_power": (p["unit"] if p is not None else np.nan),
                    "unit_energy": (e["unit"] if e is not None else np.nan),
                    "value_power": v_p,
                    "value_energy": (float(e["value"]) if e is not None else np.nan),
                    "capacity_power": cap_p,
                    "capacity_energy": (float(e["capacity"]) if e is not None else np.nan),
                    "capacity_ceiling_power": ceil_p,
                    "capacity_ceiling_energy": (float(e["capacity_ceiling"])
                                                if e is not None else np.nan),
                    "vbasis_power": (p["vbasis"] if p is not None else np.nan),
                    "case": case,
                    "rc_mathematical": rc_p,
                    "e2p": D,
                    "capex_power": cx_p,
                    "capex_energy": cx_e,
                    "C_bundle": C_bundle,
                    "RC_power": delta,
                    "RC_energy": delta,
                    "ratio_power_reduction": ratio_p,
                    "ratio_energy_reduction": ratio_e,
                    "ratio_reduction_proportional": f_prop,
                    "rc_reliable": rc_reliable,
                })
            st_df = pd.DataFrame(rows).sort_values([tcol, ncol, ycol])
            fpath = self.name_dir.joinpath("capacity_addition_analysis_storage.csv")
            st_df.to_csv(fpath, index=False)
            logging.info(f"Classified storage RC analysis saved to {fpath} "
                         f"({len(st_df)} rows)")

    def _generate_rc_heatmaps(self):
        """Render the RC heatmaps for this scenario's classified analyses.

        Opt-in via config analysis.generate_rc_heatmaps. Loads the standalone
        rc_heatmaps.py (repository root) by file path, so the plotting logic has a
        single source of truth and the standalone stays usable on its own with
        custom options (--vmax, --storage-metric, ...). Operates on self.name_dir,
        which already holds the capacity_addition_analysis_*.csv written above.
        """
        import importlib.util
        # rc_heatmaps.py sits at the repo root (sibling of the zen_garden package).
        candidates = [
            Path(__file__).resolve().parents[2] / "rc_heatmaps.py",
            Path.cwd() / "rc_heatmaps.py",
        ]
        script = next((p for p in candidates if p.is_file()), None)
        if script is None:
            logging.warning("generate_rc_heatmaps: rc_heatmaps.py not found "
                            "(expected at repository root) — heatmaps skipped")
            return
        spec = importlib.util.spec_from_file_location("rc_heatmaps", str(script))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.run(str(self.name_dir), vmax=100.0, storage_metric="proportional",
                annotate=True)
        logging.info(f"RC heatmaps generated under {self.name_dir.joinpath('heatmaps')}")

    def dump_rc_decomposition(self):
        """Diagnostic: exact per-constraint decomposition of the reduced cost of
        capacity_addition for configured targets.

        For each target the TRUE reduced cost is computed from the solved model as
            RC_true = obj_coef(var) - sum_over_constraints( coef_in_constraint * dual )
        and split by constraint, flagging which constraints the rc_capex_equivalent
        reconstruction actually captures (lifetime + diffusion [+ storage e2p_min]).
        This reveals whether an UNcaptured constraint (e.g. constraint_capacity_coupling,
        construction_time, min/max_capacity_addition) carries a contribution the
        reconstruction misses — i.e. why the reconstructed RC can be wrong.

        Opt-in via config:
          analysis.rc_dual_dump = true
          analysis.rc_dual_dump_targets = [{"tech","node"[, "capacity_type"]}]
        Writes rc_dual_decomposition.csv next to capacity_addition_analysis.csv.
        """
        targets = getattr(self.analysis, "rc_dual_dump_targets", []) or []
        if not targets:
            return
        model = self.model
        lab = model.variables["capacity_addition"].labels
        # objective coefficients (capacity_addition has none for conversion, but be general)
        try:
            oexpr = model.objective.expression
            ovars = np.asarray(oexpr.vars.values)
            ocoef = np.asarray(oexpr.coeffs.values)
        except Exception:
            ovars = ocoef = None
        captured = {"constraint_technology_lifetime",
                    "constraint_technology_diffusion_limit",
                    "constraint_technology_diffusion_limit_total",
                    "constraint_capacity_energy_to_power_ratio_min"}
        try:
            comp = pd.read_csv(self.name_dir.joinpath("rc_components.csv"))
        except Exception:
            comp = None
        try:
            capdf = pd.read_csv(self.name_dir.joinpath("capacity_addition_analysis.csv"))
        except Exception:
            capdf = None

        def _lookup(dfx, tech, ctype, node, y, col):
            if dfx is None:
                return np.nan
            m = dfx[(dfx.set_technologies == tech) & (dfx.set_capacity_types == ctype)
                    & (dfx.set_location == node) & (dfx.set_time_steps_yearly == y)]
            return float(m[col].iloc[0]) if len(m) else np.nan

        rows = []
        for t in targets:
            tech, node = t["tech"], t["node"]
            ctype = t.get("capacity_type", "power")
            try:
                sub = lab.sel(set_technologies=tech, set_capacity_types=ctype,
                              set_location=node)
            except Exception as e:
                logging.warning(f"rc_dual_dump: target {t} not found ({e})")
                continue
            for y in [int(v) for v in np.atleast_1d(sub["set_time_steps_yearly"].values)]:
                L = int(sub.sel(set_time_steps_yearly=y).item())
                if L < 0:
                    continue
                contribs = {}
                for cname, con in model.constraints.items():
                    dual = getattr(con, "dual", None)
                    vv = getattr(con, "vars", None)
                    if dual is None or vv is None or "_term" not in vv.dims:
                        continue
                    if not (np.asarray(vv.values) == L).any():
                        continue
                    coef_row = con.coeffs.where(vv == L, 0.0).sum("_term")
                    contrib = float((coef_row * dual.fillna(0.0)).sum().item())
                    if abs(contrib) > 1e-12:
                        contribs[cname] = contrib
                obj_coef = (float(ocoef[ovars == L].sum())
                            if (ovars is not None and (ovars == L).any()) else 0.0)
                rc_true_obj = obj_coef - sum(contribs.values())
                scaling = _lookup(comp, tech, ctype, node, y, "scaling")
                rc_recon = _lookup(capdf, tech, ctype, node, y, "rc_capex_equivalent")
                rc_true_capex = (rc_true_obj / scaling
                                 if (scaling == scaling and scaling) else np.nan)
                for cname, c in sorted(contribs.items(), key=lambda kv: -abs(kv[1])):
                    rows.append(dict(tech=tech, node=node, capacity_type=ctype, year_idx=y,
                                     constraint=cname, contribution_obj=c,
                                     captured=(cname in captured)))
                for label, val in (("== RC_true (obj units) ==", rc_true_obj),
                                   ("== RC_true (capex units) ==", rc_true_capex),
                                   ("== rc_reconstructed (capex units) ==", rc_recon),
                                   ("== mismatch (true - recon, capex) ==", rc_true_capex - rc_recon)):
                    rows.append(dict(tech=tech, node=node, capacity_type=ctype, year_idx=y,
                                     constraint=label, contribution_obj=val, captured=""))
        if rows:
            f = self.name_dir.joinpath("rc_dual_decomposition.csv")
            pd.DataFrame(rows).to_csv(f, index=False)
            logging.info(f"RC dual decomposition saved to {f}")

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
