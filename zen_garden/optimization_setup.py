"""Class defining the optimization model.

The class takes as inputs the properties of the optimization problem. The
properties are saved in the dictionaries analysis and system which are passed
to the class. After initializing the model, the class adds carriers and
technologies to the model and returns it. The class also includes a method to
solve the optimization problem.
"""

import copy
import logging
import os
from collections import defaultdict

import linopy as lp
import numpy as np
import pandas as pd
import xarray as xr

from zen_garden.model.component import Constraint, IndexSet, Parameter, Variable
from zen_garden.model.element import Element
from zen_garden.model.energy_system import EnergySystem
from zen_garden.model.technology.technology import Technology
from zen_garden.preprocess.parameter_change_log import parameter_change_log
from zen_garden.preprocess.time_series_aggregation import TimeSeriesAggregation
from zen_garden.preprocess.unit_handling import Scaling
from zen_garden.utils import IISConstraintParser, ScenarioDict, StringUtils


class OptimizationSetup(object):
    """Class defining the optimization model.

    The class takes as inputs the properties of the optimization problem. The 
    properties are saved in the dictionaries analysis and system which are 
    passed to the class. After initializing the model, the class adds carriers 
    and technologies to the model and returns it. The class also includes a \
    method to solve the optimization problem.
    """

    # dict of element classes, this dict is filled in the __init__ of the package
    dict_element_classes = {}

    def __init__(self, config, scenario_dict: dict, input_data_checks):
        """Setup optimization of the energy system.

        This function sets up the optimization process for the energy system
        using the provided configuration, scenario data, and input data checks.

        Args:
            config (Config): Config object used to extract the analysis, system,
                and solver dictionaries.
            scenario_dict (dict): Dictionary defining the scenario, including
                data such as resources, demand, etc.
            input_data_checks (InputDataChecks): Input data checks object to
                verify the integrity of the input data.

        """
        self.analysis = copy.deepcopy(config.analysis)
        self.system = copy.deepcopy(config.system)
        self.solver = copy.deepcopy(config.solver)
        self.input_data_checks = input_data_checks
        self.input_data_checks.optimization_setup = self
        # create a dictionary with the paths to access the model inputs
        # check if input data exists
        self.create_paths()
        # dict to update elements according to scenario
        self.scenario_dict = ScenarioDict(scenario_dict, self, self.paths)
        # check if all needed data inputs for the chosen technologies exist
        # remove non-existent inputs
        self.input_data_checks.check_existing_technology_data()
        # empty dict of elements (will be filled with class_name: instance_list)
        self.dict_elements = defaultdict(list)
        # read the parameter change log
        self.parameter_change_log = parameter_change_log()
        # optimization model
        self.model = None
        # eps used by the RC objective perturbation (set in perturb_objective_for_rc)
        self.rc_perturbation_eps = None
        # the components
        self.variables = None
        self.parameters = None
        self.constraints = None
        self.sets = None

        # initiate dictionary for storing extra year data
        self.year_specific_ts = {}

        # sorted list of class names
        element_classes = self.dict_element_classes.keys()
        carrier_classes = [
            element_name
            for element_name in element_classes
            if "Carrier" in element_name
        ]
        technology_classes = [
            element_name
            for element_name in element_classes
            if "Technology" in element_name
        ]
        self.element_list = technology_classes + carrier_classes

        # step of optimization horizon
        self.step_horizon = 0

        # Init the energy system
        self.energy_system = EnergySystem(optimization_setup=self)

        # add Elements to optimization
        self.add_elements()

        # check if all elements from the scenario_dict are in the model
        ScenarioDict.check_if_all_elements_in_model(
            self.scenario_dict, self.dict_elements
        )

        # The time series aggregation
        self.time_series_aggregation = None

        # set base scenario
        self.set_base_configuration()

        # read input data into elements
        self.read_input_csv()

        # conduct consistency checks of input units
        self.energy_system.unit_handling.consistency_checks_input_units(
            optimization_setup=self
        )

        # conduct time series aggregation
        self.time_series_aggregation = TimeSeriesAggregation(
            energy_system=self.energy_system
        )

    def create_paths(self):
        """This method creates a dictionary with the paths of the data split
        by carriers, networks, technologies.
        """
        ## General Paths
        # define path to access dataset related to the current analysis
        self.path_data = self.analysis.dataset
        assert os.path.exists(
            self.path_data
        ), f"Folder for input data {self.analysis.dataset} does not exist!"
        self.input_data_checks.check_primary_folder_structure()
        self.paths = dict()
        # create a dictionary with the keys based on the folders in path_data
        for folder_name in next(os.walk(self.path_data))[1]:
            self.paths[folder_name] = dict()
            self.paths[folder_name]["folder"] = os.path.join(
                self.path_data, folder_name
            )
        # add element paths and their file paths
        stack = [self.analysis.subsets]
        while stack:
            cur_dict = stack.pop()
            for set_name, subsets in cur_dict.items():
                path = self.paths[set_name]["folder"]
                if isinstance(subsets, dict):
                    stack.append(subsets)
                    self.add_folder_paths(set_name, path, list(subsets.keys()))
                else:
                    self.add_folder_paths(set_name, path, subsets)
                    for element in subsets:
                        if self.system[element]:
                            self.add_folder_paths(
                                element, self.paths[element]["folder"]
                            )

    def add_folder_paths(self, set_name, path, subsets=None):
        """Add file paths of element to paths dictionary.

        :param set_name: name of set
        :param path: path to folder
        :param subsets: list of subsets
        """
        if subsets is None:
            subsets = []
        for element in next(os.walk(path))[1]:
            if element not in subsets:
                self.paths[set_name][element] = dict()
                self.paths[set_name][element]["folder"] = os.path.join(path, element)
                sub_path = os.path.join(path, element)
                for file in next(os.walk(sub_path))[2]:
                    self.paths[set_name][element][file] = os.path.join(sub_path, file)
                # add element paths to parent sets
                parent_sets = self._find_parent_set(self.analysis.subsets, set_name)
                for parent_set in parent_sets:
                    self.paths[parent_set][element] = self.paths[set_name][element]
            else:
                self.paths[element] = dict()
                self.paths[element]["folder"] = os.path.join(path, element)

    def _find_parent_set(self, dictionary, subset, path=None):
        """This method finds the parent sets of a subset.

        :param dictionary: dictionary of subsets
        :param subset: subset to find parent sets of
        :param path: path to subset
        :return: list of parent sets
        """
        if path is None:
            path = []
        for key, value in dictionary.items():
            current_path = path + [key]
            if subset in dictionary[key]:
                return current_path
            elif isinstance(value, dict):
                result = self._find_parent_set(value, subset, current_path)
                if result:
                    return result
        return []

    def add_elements(self):
        """Set up the parameters, variables and constraints of the carriers."""
        logging.info("\n--- Add elements to model--- \n")
        for element_name in self.element_list:
            element_class = self.dict_element_classes[element_name]
            element_name = element_class.label
            element_set = self.system[element_name]

            # before adding the carriers, get set_carriers
            # check if carrier data exists
            if element_name == "set_carriers":
                element_set = self.energy_system.set_carriers
                self.system.set_carriers = element_set
                self.input_data_checks.check_existing_carrier_data()

            # check if element_set has a subset and remove subset from element_set
            if element_name in self.analysis.subsets.keys():
                if isinstance(self.analysis.subsets[element_name], list):
                    subset_names = self.analysis.subsets[element_name]
                elif isinstance(self.analysis.subsets[element_name], dict):
                    subset_names = self.analysis.subsets[element_name].keys()
                else:
                    raise ValueError(
                        f"Subset {element_name} has to be either a list or a dict"
                    )
                element_subset = [
                    item for subset in subset_names for item in self.system[subset]
                ]
            else:
                stack = [
                    _dict
                    for _dict in copy.deepcopy(self.analysis.subsets).values()
                    if isinstance(_dict, dict)
                ]
                while stack:  # check if element_set is a subset of a subset
                    cur_dict = stack.pop()
                    element_subset = []
                    for set_name, subsets in cur_dict.items():
                        if element_name == set_name:
                            if isinstance(subsets, list):
                                element_subset += [
                                    item
                                    for subset_name in subsets
                                    for item in self.system[subset_name]
                                ]
                        if isinstance(subsets, dict):
                            stack.append(subsets)
            element_set = list(set(element_set) - set(element_subset))

            element_set.sort()
            # add element class
            for item in element_set:
                self.add_element(element_class, item)

    def read_input_csv(self):
        """Read the input and conducts the time series aggregation."""
        logging.info("\n--- Read input data of elements --- \n")
        self.energy_system.store_input_data()
        for element in self.dict_elements["Element"]:
            element_class = [
                k
                for k, v in self.dict_element_classes.items()
                if v == element.__class__
            ][0]
            logging.info(f"Create {element_class} {element.name}")
            element.store_input_data()

    def add_element(self, element_class, name):
        """Add an element to the element_dict with the class labels as key.

        Args:
            element_class: Class of the element
            name: Name of the element
        """
        # get the instance
        instance = element_class(name, self)
        # add to class specific list
        self.dict_elements[element_class.__name__].append(instance)
        # Add the instance to all parents as well
        for cls in element_class.__mro__:
            if not cls == element_class:
                self.dict_elements[cls.__name__].append(instance)

    def get_all_elements(self, cls):
        """Get all elements of the class in the energy system."""
        return self.dict_elements[cls.__name__]

    def get_all_names_of_elements(self, cls):
        """Get all names of elements in class.

        :param cls: class of the elements to return
        :return: names_of_elements: list of elements in this class
        """
        _elements_in_class = self.get_all_elements(cls=cls)
        names_of_elements = []
        for _element in _elements_in_class:
            names_of_elements.append(_element.name)
        return names_of_elements

    def get_element(self, cls, name: str):
        """Get single element in class by name.

        :param name: name of element
        :param cls: class of the elements to return
        :return: element: return element whose name is matched
        """
        for element in self.get_all_elements(cls=cls):
            if element.name == name:
                return element
        return None

    def get_element_class(self, name: str):
        """Get element class by name. If not an element class, return None.

        :param name: name of element class
        :return: element_class: return element whose name is matched
        """
        element_classes = {
            self.dict_element_classes[class_name].label: self.dict_element_classes[
                class_name
            ]
            for class_name in self.dict_element_classes
        }
        if name in element_classes.keys():
            return element_classes[name]
        else:
            return None

    def get_class_set_of_element(self, element_name: str, klass):
        """Returns the set of all elements in the class of the element.

        :param element_name: name of element
        :param klass: class of the elements to return
        :return: class_set: set of all elements in the class of the element
        """
        class_name = self.get_element(klass, element_name).__class__.label
        class_set = self.sets[class_name]
        return class_set

    def get_attribute_of_all_elements(
        self,
        cls,
        attribute_name: str,
        capacity_types=False,
        return_attribute_is_series=False,
    ):
        """Get attribute values of all elements in a class.

        Args:
            cls: class of the elements to return
            attribute_name (str): name of attribute
            capacity_types (boolean): if attributes extracted for all capacity types
            return_attribute_is_series (boolean): if information on attribute type is
                returned
            dict_of_attributes (dict): dict of attribute values
            attribute_is_series: return information on attribute type
        """
        class_elements = self.get_all_elements(cls=cls)
        dict_of_attributes = {}
        dict_of_units = {}
        attribute_is_series = False
        for element in class_elements:
            if not capacity_types:
                dict_of_attributes, attribute_is_series_temp, dict_of_units = (
                    self.append_attribute_of_element_to_dict(
                        element, attribute_name, dict_of_attributes, dict_of_units
                    )
                )
                if attribute_is_series_temp:
                    attribute_is_series = attribute_is_series_temp
            # if extracted for both capacity types
            else:
                for capacity_type in self.system.set_capacity_types:
                    # append energy only for storage technologies
                    if (
                        capacity_type == self.system.set_capacity_types[0]
                        or element.name in self.system.set_storage_technologies
                    ):
                        dict_of_attributes, attribute_is_series_temp, dict_of_units = (
                            self.append_attribute_of_element_to_dict(
                                element,
                                attribute_name,
                                dict_of_attributes,
                                dict_of_units,
                                capacity_type,
                            )
                        )
                        if attribute_is_series_temp:
                            attribute_is_series = attribute_is_series_temp
        if return_attribute_is_series:
            return dict_of_attributes, dict_of_units, attribute_is_series
        else:
            return dict_of_attributes

    def append_attribute_of_element_to_dict(
        self,
        element,
        attribute_name,
        dict_of_attributes,
        dict_of_units,
        capacity_type=None,
    ):
        """Get attribute values of all elements in this class.

        Args:
            element: element of class
            attribute_name (str): str name of attribute
            dict_of_attributes (dict): dict of attribute values
            capacity_type: capacity type for which attribute extracted. If None,
                not listed in key
            dict_of_attributes: returns dict of attribute values
        """
        attribute_is_series = False
        # add Energy for energy capacity type
        if capacity_type == self.system.set_capacity_types[1]:
            attribute_name += "_energy"
        # if element does not have attribute
        if not hasattr(element, attribute_name):
            # if attribute is time series that does not exist
            if (
                attribute_name in element.raw_time_series
                and element.raw_time_series[attribute_name] is None
            ):
                return dict_of_attributes, None, dict_of_units
            else:
                raise AssertionError(
                    f"Element {element.name} does not have attribute {attribute_name}"
                )
        attribute = getattr(element, attribute_name)
        assert not isinstance(attribute, pd.DataFrame), (
            "Not yet implemented for pd.DataFrames. Wrong format for"
            f"element {element.name}"
        )
        # add attribute to dict_of_attributes
        if attribute is None:
            return dict_of_attributes, False, dict_of_units
        elif isinstance(attribute, dict):
            dict_of_attributes.update(
                {(element.name,) + (key,): val for key, val in attribute.items()}
            )
        elif isinstance(attribute, pd.Series):
            if capacity_type:
                combined_key = (element.name, capacity_type)
            else:
                combined_key = element.name
            if attribute_name in element.units:
                if attribute_name in [
                    "conversion_factor",
                    "retrofit_flow_coupling_factor",
                ]:
                    dict_of_units[combined_key] = element.units[attribute_name]
                else:
                    dict_of_units[combined_key] = element.units[attribute_name][
                        "unit_in_base_units"
                    ].units
            else:
                # needed since these
                if attribute_name == "capex_capacity_existing":
                    dict_of_units[combined_key] = element.units["opex_specific_fixed"][
                        "unit_in_base_units"
                    ].units
                elif attribute_name == "capex_capacity_existing_energy":
                    dict_of_units[combined_key] = element.units[
                        "opex_specific_fixed_energy"
                    ]["unit_in_base_units"].units
                elif attribute_name == "capex_specific_transport":
                    dict_of_units[combined_key] = element.units["opex_specific_fixed"][
                        "unit_in_base_units"
                    ].units
                elif attribute_name == "capex_per_distance_transport":
                    base_units = self.energy_system.unit_handling.base_units.items()
                    length_base_unit = [
                        key for key, value in base_units if value == "[length]"
                    ][0]
                    dict_of_units[combined_key] = element.units["opex_specific_fixed"][
                        "unit_in_base_units"
                    ].units / self.energy_system.unit_handling.ureg(length_base_unit)
            if len(attribute) > 1:
                dict_of_attributes[combined_key] = attribute
                attribute_is_series = True
            else:
                if attribute.index == 0:
                    dict_of_attributes[combined_key] = attribute.squeeze()
                    attribute_is_series = False
                # since single-directed edges are allowed to exist (e.g. CH-DE exists,
                # DE-CH doesn't), TransportTechnology attributes shared with other
                # technologies (such as capacity existing)
                # mustn't be squeezed even-though the attributes length is smaller than
                # 1. Otherwise, pd.concat(dict_of_attributes) messes up in
                # initialize_component(), leading to an error further on in the code.
                else:
                    dict_of_attributes[combined_key] = attribute
                    attribute_is_series = True
        elif isinstance(attribute, int):
            if capacity_type:
                dict_of_attributes[(element.name, capacity_type)] = [attribute]
            else:
                dict_of_attributes[element.name] = [attribute]
        else:
            if capacity_type:
                dict_of_attributes[(element.name, capacity_type)] = attribute
            else:
                dict_of_attributes[element.name] = attribute
        return dict_of_attributes, attribute_is_series, dict_of_units

    def get_attribute_of_specific_element(
        self, cls, element_name: str, attribute_name: str
    ):
        """Get attribute of specific element in class.

        :param cls: class of the elements to return
        :param element_name: str name of element
        :param attribute_name: str name of attribute
        :return: attribute_value: value of attribute
        """
        # get element
        element = self.get_element(cls, element_name)
        # assert that _element exists and has attribute
        assert element, f"Element {element_name} not in class {cls.__name__}"
        assert hasattr(
            element, attribute_name
        ), f"Element {element_name} does not have attribute {attribute_name}"
        attribute_value = getattr(element, attribute_name)
        return attribute_value

    def construct_optimization_problem(self):
        """Constructs the optimization problem."""
        # create empty ConcreteModel
        if self.solver.solver_dir is not None and not os.path.exists(
            self.solver.solver_dir
        ):
            os.makedirs(self.solver.solver_dir)
        self.model = lp.Model(solver_dir=self.solver.solver_dir)
        # we need to reset the components to not carry them over
        self.sets = IndexSet()
        self.variables = Variable(self)
        self.parameters = Parameter(self)
        self.constraints = Constraint(self.sets, self.model)
        # define and construct components of self.model
        Element.construct_model_components(self)
        # Initiate scaling object
        self.scaling = Scaling(
            self.model, self.solver.scaling_algorithm, self.solver.scaling_include_rhs
        )

    def get_optimization_horizon(self):
        """Returns list of optimization horizon steps."""
        # if using rolling horizon
        if self.system.use_rolling_horizon:
            assert (
                self.system.years_in_rolling_horizon
                >= self.system.years_in_decision_horizon
            ), (
                "There must be at least the same number of years in the rolling"
                "horizon as the decision horizon. years_in_rolling_horizon"
                f"({self.system.years_in_rolling_horizon}) < years_in_decision_horizon "
                f"({self.system.years_in_decision_horizon})"
            )
            self.years_in_horizon = self.system.years_in_rolling_horizon
            time_steps_yearly = self.energy_system.set_time_steps_yearly
            # skip years_in_decision_horizon years
            self.optimized_time_steps = [
                year
                for year in time_steps_yearly
                if (
                    year % self.system.years_in_decision_horizon == 0
                    or year == time_steps_yearly[-1]
                )
            ]
            self.steps_horizon = {
                year: list(
                    range(
                        year,
                        min(year + self.years_in_horizon, max(time_steps_yearly) + 1),
                    )
                )
                for year in self.optimized_time_steps
            }
        # if no rolling horizon
        else:
            self.years_in_horizon = len(self.energy_system.set_time_steps_yearly)
            self.optimized_time_steps = [0]
            self.steps_horizon = {0: self.energy_system.set_time_steps_yearly}
        return list(self.steps_horizon.keys())

    def get_decision_horizon(self, step_horizon):
        """Return the decision horizon.

        Returns the decision horizon for the optimization step, i.e., the time
        steps for which the decisions are saved.

        :param step_horizon: step of the rolling horizon
        :return: decision_horizon: list of time steps in the decision horizon
        """
        if step_horizon == self.optimized_time_steps[-1]:
            decision_horizon = [step_horizon]
        else:
            next_optimization_step = self.optimized_time_steps[
                self.optimized_time_steps.index(step_horizon) + 1
            ]
            decision_horizon = list(range(step_horizon, next_optimization_step))
        return decision_horizon

    def set_base_configuration(self, scenario="", elements=None):
        """Set base configuration.

        :param scenario: name of base scenario
        :param elements: elements in base configuration
        """
        if elements is None:
            elements = {}
        self.base_scenario = scenario
        self.base_configuration = elements

    def overwrite_time_indices(self, step_horizon):
        """Select subset of time indices, matching the step horizon.

        :param step_horizon: step of the rolling horizon
        """
        if self.system.use_rolling_horizon:
            self.step_horizon = step_horizon
            time_steps_yearly_horizon = self.steps_horizon[step_horizon]
            base_time_steps_horizon = (
                self.energy_system.time_steps.decode_yearly_time_steps(
                    time_steps_yearly_horizon
                )
            )
            # overwrite aggregated time steps - operation
            set_time_steps_operation = self.energy_system.time_steps.encode_time_step(
                base_time_steps=base_time_steps_horizon, time_step_type="operation"
            )
            # overwrite aggregated time steps - storage
            set_time_steps_storage = self.energy_system.time_steps.encode_time_step(
                base_time_steps=base_time_steps_horizon, time_step_type="storage"
            )
            # copy invest time steps
            time_steps_operation = set_time_steps_operation.squeeze().tolist()
            time_steps_storage = set_time_steps_storage.squeeze().tolist()
            if isinstance(time_steps_operation, int):
                time_steps_operation = [time_steps_operation]
                time_steps_storage = [time_steps_storage]
            self.energy_system.time_steps.time_steps_operation = time_steps_operation
            self.energy_system.time_steps.time_steps_storage = time_steps_storage
            # overwrite base time steps and yearly base time steps
            new_base_time_steps_horizon = base_time_steps_horizon.squeeze().tolist()
            if not isinstance(new_base_time_steps_horizon, list):
                new_base_time_steps_horizon = [new_base_time_steps_horizon]
            self.energy_system.set_base_time_steps = new_base_time_steps_horizon
            self.energy_system.set_time_steps_yearly = time_steps_yearly_horizon

    def apply_parameter_overrides_for_rc(self):
        """Apply optional config-driven parameter overrides for RC experiments.

        Hooked into Element.construct_model_components() AFTER construct_params and
        BEFORE construct_vars/constraints/objective, so the overridden values flow
        into the capex cost terms and the energy-to-power-ratio constraints. No-op
        unless the keys are set. Both keys are popped so they are not forwarded to
        the solver.

        config solver.solver_options:
          rc_capex_override : list of dicts, each
              {"tech", "node", "year", "value"[, "capacity_type"]}.
            Sets capex_specific_<class>[tech,(capacity_type,)node,year] so that it
            corresponds to `value` in input-file units (Euro/kW). Lets one move the
            reduced cost of a SINGLE node/year without touching the dataset (RC is a
            per-node quantity). Exact for kW-reference techs (the normal case).
          rc_tight_e2p : dict {tech: duration_h}. Fixes
            energy_to_power_ratio_min = energy_to_power_ratio_max = duration for that
            storage technology (forces a fixed duration and enables the storage-power
            RC perturbation). Empty/absent = off.
        """
        so = self.solver.solver_options
        # This hook fires once per element class (Element.construct_model_components),
        # interleaved with each class's construct_params. The target parameters do NOT
        # all exist on the first call — capex_specific_conversion is created by the
        # conversion technology, energy_to_power_ratio_* by storage. So we CACHE the
        # overrides on first sight (popping the keys so they are not forwarded to the
        # solver) and re-apply from the cache on every call, touching only the entries
        # whose target parameter already exists. Re-applying an already-set value is a
        # no-op (guarded below), so the net effect is "apply exactly once, as soon as
        # the relevant parameter exists and before its class builds its cost terms".
        if "rc_capex_override" in so:
            self._rc_capex_override = so.pop("rc_capex_override")
        if "rc_tight_e2p" in so:
            self._rc_tight_e2p = so.pop("rc_tight_e2p")
        capex_ov = getattr(self, "_rc_capex_override", None)
        tight_e2p = getattr(self, "_rc_tight_e2p", None)
        if not capex_ov and not tight_e2p:
            return

        try:
            fraction_year = (self.system.unaggregated_time_steps_per_year
                             / self.system.total_hours_per_year)
        except Exception:
            fraction_year = 1.0
        try:
            ref_year = int(self.system.reference_year)
            interval = int(self.system.interval_between_years) or 1
        except Exception:
            ref_year, interval = 0, 1

        def _dim(dims, *needles):
            return next((d for d in dims for n in needles if n in d), None)

        # ---- per-(tech, node, year) capex overrides --------------------------
        if capex_ov:
            class_param = {"conversion": "capex_specific_conversion",
                           "transport": "capex_specific_transport",
                           "storage": "capex_specific_storage"}

            def tech_class(t):
                for cls_, sname in (("conversion", "set_conversion_technologies"),
                                    ("transport", "set_transport_technologies"),
                                    ("storage", "set_storage_technologies"),
                                    ("conversion", "set_retrofitting_technologies")):
                    try:
                        if t in self.sets[sname]:
                            return cls_
                    except Exception:
                        pass
                return None

            for entry in capex_ov:
                try:
                    tech, node = entry["tech"], entry["node"]
                    val, year = float(entry["value"]), int(entry["year"])
                except Exception as e:
                    logging.warning(f"rc_capex_override: bad entry {entry} ({e}) — skipped")
                    continue
                cls_ = tech_class(tech)
                p = getattr(self.parameters, class_param.get(cls_, ""), None) if cls_ else None
                if p is None:
                    # parameter not constructed yet on this hook call (capex_specific_*
                    # is created by its own technology class) — retried on a later call.
                    continue
                dims = list(p.dims)
                sel = {_dim(dims, "technolog"): tech,
                       _dim(dims, "node", "location", "edge"): node,
                       _dim(dims, "year"): (year - ref_year) // interval}
                ctype_dim = _dim(dims, "capacity_type")
                if ctype_dim is not None:
                    sel[ctype_dim] = entry.get("capacity_type", "power")
                model_val = val * fraction_year
                try:
                    cur = p.loc[sel]
                    curv = np.asarray(cur.values, dtype=float)
                    if curv.size and np.all(np.isnan(curv) | np.isclose(curv, model_val)):
                        continue  # already applied (or only-NaN structure) — no-op
                    # preserve NaN structure (e.g. unused set_capex_linear segments)
                    p.loc[sel] = cur.where(np.isnan(cur), model_val)
                    logging.info(f"rc_capex_override: {class_param[cls_]}[{sel}] -> "
                                 f"{model_val} (input {val} * fraction_year {fraction_year})")
                except Exception as e:
                    logging.warning(f"rc_capex_override: could not set {sel} on "
                                    f"{class_param[cls_]}: {e}")

        # ---- fixed (tight) energy-to-power ratio per storage tech ------------
        if tight_e2p:
            e2p_min = getattr(self.parameters, "energy_to_power_ratio_min", None)
            e2p_max = getattr(self.parameters, "energy_to_power_ratio_max", None)
            if e2p_min is None or e2p_max is None:
                pass  # storage params not built yet on this call — retried later
            else:
                sdim = _dim(list(e2p_min.dims), "technolog")
                for tech, dur in dict(tight_e2p).items():
                    try:
                        d = float(dur)
                        if np.isclose(float(e2p_min.loc[{sdim: tech}]), d) and \
                                np.isclose(float(e2p_max.loc[{sdim: tech}]), d):
                            continue  # already applied — no-op
                        e2p_min.loc[{sdim: tech}] = d
                        e2p_max.loc[{sdim: tech}] = d
                        logging.info(f"rc_tight_e2p: '{tech}' duration fixed to {d} h "
                                     f"(energy_to_power_ratio_min = max = {d})")
                    except Exception as e:
                        logging.warning(f"rc_tight_e2p: could not set '{tech}': {e}")

    def perturb_objective_for_rc(self):
        """Add +eps * sum(capacity_addition) to the objective to break dual
        degeneracy at unbuilt technologies.

        At an unbuilt technology the lifetime equality leaves the capex
        cost-attribution between the lifetime dual and the linear-capex dual a
        free, objective-flat degree of freedom (a degenerate dual face). A small
        positive perturbation makes capacity_addition strictly prefer its lower
        bound 0 -> it becomes non-basic -> capacity becomes basic in the lifetime
        equality -> the economically correct dual endpoint (t_lo, carrying the
        genuine marginal value) is selected. As eps -> 0 the primal optimum is
        unchanged and the dual converges exactly to that endpoint.

        Controlled via config: solver.solver_options["rc_perturbation"] = <eps>.
        The key is popped here so it is not forwarded to Gurobi as an option.
        """
        eps = self.solver.solver_options.pop("rc_perturbation", None)
        if not eps:
            return
        # store so postprocessing can subtract the eps contribution from the
        # native reduced cost (reduced_cost_corrected)
        self.rc_perturbation_eps = eps
        capacity_addition = self.model.variables["capacity_addition"]
        new_expr = self.model.objective.expression + eps * capacity_addition.sum()
        self.model.add_objective(
            new_expr, overwrite=True, sense=self.model.objective.sense
        )
        logging.info(
            f"RC perturbation: added +{eps} * sum(capacity_addition) to objective"
        )

    def perturb_lifetime_rhs_for_rc(self):
        """Add +delta to the RHS of constraint_technology_lifetime (a phantom
        existing capacity) to break PRIMAL degeneracy at unbuilt technologies.

        At an unbuilt technology capacity and capacity_addition are both 0, so the
        lifetime equality (capacity - sum(capacity_addition) = capacity_existing)
        reads 0 = 0 and its dual lambda is non-unique (a whole interval
        [-K, -V], K = annualised capex, V = marginal value of capacity). The dual
        objective contributes capacity_existing * lambda = 0 * lambda, i.e. it is
        flat in lambda -> the solver cannot select an endpoint and the
        reconstructed rc_capex_equivalent may collapse to a spurious 0.

        Adding a tiny POSITIVE delta to the RHS makes the dual objective term
        delta * lambda, whose maximiser over the (unchanged) feasible interval is
        the value endpoint lambda = -V. This pins the lifetime dual to the
        economically correct endpoint, so rc_capex_equivalent reports the true
        distance-to-build. As delta -> 0 the primal optimum is unchanged
        (capacity_addition stays 0; only capacity picks up the phantom delta).

        This is an RHS perturbation and is the correct knob for this (primal)
        degeneracy. Contrast rc_perturbation, which perturbs the OBJECTIVE: that
        only shifts the dual-feasible interval and, because the dual objective
        stays flat in lambda, cannot select within it.

        Only genuinely degenerate GREENFIELD entries are perturbed: existing == 0
        (RHS == 0) AND min(capacity upper bound, capacity_limit) >= delta.

        The greenfield restriction matters because the 0 = 0 degeneracy only
        exists where existing == 0. Brownfield technologies (existing != 0) have
        capacity > 0 and hence a non-degenerate lifetime dual already -- they
        neither need the perturbation nor tolerate it (e.g. reservoir_hydro at a
        node with existing == capacity_limit would become infeasible, because
        capacity = existing + delta > capacity_limit).

        The head-room check (ceiling = min(capacity.upper, capacity_limit) >=
        delta) additionally skips greenfield technologies that cannot host delta
        at all: capacity_limit < delta, or on/off techs with
        capacity_addition_max == 0 whose capacity upper bound is 0
        (capacity.upper folds in capacity_addition_max via capacity_bounds() in
        technology.py).

        Controlled via config:
        solver.solver_options["rc_lifetime_rhs_perturbation"] = <delta> in
        capacity units (e.g. GW). The key is popped here so it is not forwarded
        to Gurobi. Set to None/0 to disable.
        """
        delta = self.solver.solver_options.pop("rc_lifetime_rhs_perturbation", None)
        if not delta:
            return
        name = "constraint_technology_lifetime"
        if name not in self.model.constraints:
            logging.warning(
                f"RC lifetime-RHS perturbation: '{name}' not in model — skipped"
            )
            return
        con = self.model.constraints[name]
        rhs_da = con.rhs
        try:
            # Capacity head-room = min(variable upper bound, capacity_limit);
            # both can bind (see docstring / capacity_bounds() in technology.py).
            cap_upper = xr.align(
                rhs_da, self.model.variables["capacity"].upper, join="left"
            )[1].fillna(np.inf)
            cap_limit = xr.align(
                rhs_da, self.parameters.capacity_limit, join="left"
            )[1].fillna(np.inf)
            ceiling = np.minimum(cap_upper, cap_limit)
            # Perturb only degenerate greenfield entries (existing == 0) that
            # have room for delta; skip brownfield and no-room techs (the
            # docstring explains why both conditions are required to stay
            # feasible).
            is_greenfield = np.abs(rhs_da) < 1e-9
            # Storage is handled separately by perturb_storage_power_addition_for_rc():
            # the lifetime-RHS phantom lands in *capacity*, but the energy-to-power
            # ratio constraint reads *capacity_addition*, so a capacity-side phantom
            # would leave the two storage components decoupled. Exclude all storage
            # technologies here so the two perturbations do not overlap.
            storage_techs = list(self.sets["set_storage_technologies"])
            is_storage = rhs_da["set_technologies"].isin(storage_techs)
            add = xr.where(
                is_greenfield & (ceiling >= delta) & ~is_storage, float(delta), 0.0
            )
            add = add.broadcast_like(rhs_da).transpose(*rhs_da.dims)
            add_data = add.data
        except Exception as exc:
            logging.error(
                f"RC lifetime-RHS perturbation: head-room guard failed ({exc}); "
                f"skipping the perturbation entirely (safer than risking "
                f"infeasibility)."
            )
            return
        n_perturbed = int(np.count_nonzero(add_data))
        n_total = int(add_data.size)
        con.rhs.data = rhs_da.data + add_data
        logging.info(
            f"RC perturbation: added +{delta} to RHS of {name} "
            f"({n_perturbed}/{n_total} entries perturbed; "
            f"{n_total - n_perturbed} skipped for head-room < delta)"
        )

    def perturb_storage_power_addition_for_rc(self):
        """Force a tiny lower bound (yotta) on capacity_addition of storage POWER
        at unbuilt greenfield nodes so the energy-to-power-ratio constraint pulls up
        a matching energy addition — making the storage reduced cost reflect the
        *joint* (power+energy) distance-to-build instead of the decoupled
        per-component own-capex.

        Why storage needs its own knob (see docs/rc_storage_power_energy.md):
        storage is built as two separate capacities (power, energy) that couple only
        through operation. At an unbuilt node both are 0, so the marginal value of
        either component alone is 0 and each per-component reduced cost collapses to
        its own (annualised) capex. The lifetime-RHS perturbation cannot fix this:
        it places the phantom delta in *capacity*, while
        constraint_capacity_energy_to_power_ratio_min reads *capacity_addition*.
        With capacity_addition still 0 the ratio reads 0 >= 0 and its dual is 0, so
        the two components stay decoupled.

        Mechanism: raise the lower bound of capacity_addition[power] to yotta at
        genuinely unbuilt greenfield storage nodes. The ratio constraint then forces
        capacity_addition[energy] >= e2p_min * yotta, i.e. a tiny *functional* probe
        storage of duration e2p_min. Because capacity_addition[power] sits at its
        (raised) lower bound it stays NON-BASIC -> its reduced cost is well defined
        and equals the joint bundle distance
        (capex_power + e2p_min * capex_energy - V). The matching energy addition is
        basic -> its reduced cost is mechanically 0, so the bundle distance is read
        off the POWER row. As yotta -> 0 the primal optimum is unchanged.

        Note: power (the small component) is perturbed and energy (= duration *
        power, the large one) follows, so the forced energy = e2p_min * yotta stays
        well above the solver tolerance; perturbing energy instead would shrink the
        forced power by the duration and drop it below tolerance for long-duration
        storage.

        Only applied where ALL hold:
          * technology is a storage technology and capacity_type == 'power',
          * greenfield: capacity_existing == 0,
          * energy_to_power_ratio_min is finite and > 0 (else no energy follows ->
            would create a power-only probe),
          * head-room for the forced power (power_ceiling >= yotta) AND for the
            forced energy (energy_ceiling >= e2p_min * yotta). This skips blocked
            techs (e.g. capacity_limit == 0) and keeps the model feasible.

        Storage is excluded from perturb_lifetime_rhs_for_rc() so the two
        perturbations do not overlap. The dual of the ratio constraint enters the
        reconstructed RC in postprocess._compute_rc_capex_equivalent(); both must be
        kept consistent.

        Controlled via config:
        solver.solver_options["rc_storage_power_perturbation"] = <yotta> in capacity
        units (e.g. GW). Choose > solver feasibility tolerance (>> 1e-6) and smaller
        than the smallest positive capacity_limit. Popped here so it is not forwarded
        to Gurobi. Set to None/0 to disable.
        """
        yotta = self.solver.solver_options.pop("rc_storage_power_perturbation", None)
        if not yotta:
            return
        storage_techs = list(self.sets["set_storage_technologies"])
        if not storage_techs:
            return
        var = self.model.variables["capacity_addition"]
        try:
            lower = var.lower
            # head-room ceiling = min(capacity variable upper bound, capacity_limit),
            # aligned to the capacity_addition index (same dims).
            cap_upper = xr.align(
                lower, self.model.variables["capacity"].upper, join="left"
            )[1].fillna(np.inf)
            cap_limit = xr.align(
                lower, self.parameters.capacity_limit, join="left"
            )[1].fillna(np.inf)
            ceiling = np.minimum(cap_upper, cap_limit)
            # existing capacity (greenfield where 0); read from the (storage-
            # unperturbed) lifetime-constraint RHS so it is index-aligned.
            existing = xr.align(
                lower, self.model.constraints["constraint_technology_lifetime"].rhs,
                join="left",
            )[1].fillna(0.0)
            # energy_to_power_ratio_min per technology (= min duration in hours);
            # 0 for technologies where it is unset -> excluded below.
            e2p = self.parameters.energy_to_power_ratio_min.rename(
                {"set_storage_technologies": "set_technologies"}
            )
            e2p = e2p.reindex(
                set_technologies=lower.indexes["set_technologies"], fill_value=0.0
            )
            # energy-side ceiling mapped onto every (tech, node, year) so the
            # power row can check that the *forced* energy fits.
            ceiling_energy = ceiling.sel(set_capacity_types="energy")

            is_power = lower["set_capacity_types"] == "power"
            is_storage = lower["set_technologies"].isin(storage_techs)
            greenfield = existing < 1e-9
            e2p_ok = (e2p > 0) & np.isfinite(e2p)
            power_room = ceiling >= yotta
            energy_room = ceiling_energy >= (e2p * yotta)

            apply = (
                is_power & is_storage & greenfield & e2p_ok & power_room & energy_room
            )
            apply = apply.broadcast_like(lower).transpose(*lower.dims)
            new_lower = xr.where(apply, float(yotta), lower)
        except Exception as exc:
            logging.error(
                f"RC storage-power perturbation: guard failed ({exc}); skipping "
                f"the perturbation entirely (safer than risking infeasibility)."
            )
            return
        n_perturbed = int(apply.sum())
        var.lower = new_lower
        logging.info(
            f"RC perturbation: raised capacity_addition[storage,power] lower bound "
            f"to +{yotta} at {n_perturbed} greenfield storage nodes "
            f"(energy follows via energy_to_power_ratio_min)."
        )

    def solve(self):
        """Create model instance by assigning parameter values and initializing sets."""
        solver_name = self.solver.name
        # remove options that are None
        solver_options = {
            key: self.solver.solver_options[key]
            for key in self.solver.solver_options
            if self.solver.solver_options[key] is not None
        }

        logging.info(f"\n--- Solve model instance using {solver_name} ---\n")
        # disable logger temporarily
        logging.disable(logging.WARNING)

        if solver_name == "gurobi":
            self.model.solve(
                solver_name=solver_name,
                io_api=self.solver.io_api,
                keep_files=self.solver.keep_files,
                sanitize_zeros=True,
                # remaining kwargs are passed to the solver
                **solver_options,
            )
        else:
            self.model.solve(
                solver_name=solver_name,
                io_api=self.solver.io_api,
                keep_files=self.solver.keep_files,
                sanitize_zeros=True,
            )
        # enable logger
        logging.disable(logging.NOTSET)
        if self.model.termination_condition == "optimal":
            self.optimality = True
        elif self.model.termination_condition == "suboptimal":
            logging.warning("The optimization is suboptimal")
            self.optimality = True
        else:
            self.optimality = False

    def write_IIS(self, scenario=""):
        """Write an ILP file to print the IIS if infeasible and using Gurobi."""
        if (
            self.model.termination_condition == "infeasible"
            and self.solver.name == "gurobi"
        ):
            output_folder = StringUtils.get_output_folder(self.analysis)
            ilp_file = os.path.join(
                output_folder,
                f"infeasible_model_IIS{f'_{scenario}' if scenario else ''}.ilp",
            )
            logging.info(f"Writing parsed IIS to {ilp_file}")
            parser = IISConstraintParser(ilp_file, self.model)
            parser.write_parsed_output()

    def add_results_of_optimization_step(self, step_horizon):
        """Adds capacity additions and carbon emissions to the next optimization step.

        This function takes the capacity additions and carbon emissions of the
        current optimization step and adds them to the existing capacity and
        existing emissions of the next optimization step. Values from the
        currently simulated year are added as existing capacities and
        emissions for future steps.

        Args:
            step_horizon (int): The year index of the current optimization step.
                In myopic foresight, capacities and emissions from this step are
                added to existing capacities and emissions.

        Returns:
            None

        """
        decision_horizon = self.get_decision_horizon(step_horizon)
        # add newly capacity_addition of first year to existing capacity
        self.add_new_capacity_addition(decision_horizon)
        # add cumulative carbon emissions to previous carbon emissions
        self.add_carbon_emission_cumulative(decision_horizon)

    def add_new_capacity_addition(self, decision_horizon):
        """Adds the newly built capacity to the existing capacity.

        This function adds installed capacities from the current optimization
        step to existing capacities in the model. It also adds costs from the
        installed capacities to existing capacity investment. Capacity values whose
        magnitude is below that specified by the solver setting
        "rounding_decimal_points_capacity" are set to zero.

        Args:
            decision_horizon (list or int): A list of the years to transfer installed
                capacities to existing capacities.

        Returns:
            None

        """
        capacity_addition = (
            self.model.solution["capacity_addition"].to_series().dropna()
        )
        invest_capacity = (
            self.model.solution["capacity_investment"].to_series().dropna()
        )
        cost_capex_overnight = (
            self.model.solution["cost_capex_overnight"].to_series().dropna()
        )

        if self.solver.round_parameters:
            rounding_value = 10 ** (-self.solver.rounding_decimal_points_capacity)
        else:
            rounding_value = 0
        capacity_addition[capacity_addition <= rounding_value] = 0
        invest_capacity[invest_capacity <= rounding_value] = 0
        cost_capex_overnight[cost_capex_overnight <= rounding_value] = 0

        for tech in self.get_all_elements(Technology):
            # new capacity
            capacity_addition_tech = capacity_addition.loc[tech.name].unstack()
            capacity_investment = invest_capacity.loc[tech.name].unstack()
            cost_capex_tech = cost_capex_overnight.loc[tech.name].unstack()
            tech.add_new_capacity_addition_tech(
                capacity_addition_tech, cost_capex_tech, decision_horizon
            )
            tech.add_new_capacity_investment(capacity_investment, decision_horizon)

    def add_carbon_emission_cumulative(self, decision_horizon):
        """Adds current emissions to existing emissions.

        This function adds carbon emissions from the current optimization
        step to the existing carbon emissions.

        Args:
            decision_horizon (list or int): A list of the years to transfer
                emissions to existing emissions.

        Returns:
            None

        """
        interval_between_years = self.energy_system.system.interval_between_years
        last_year = decision_horizon[-1]
        carbon_emissions_cumulative = (
            self.model.solution["carbon_emissions_cumulative"].loc[last_year].item()
        )
        carbon_emissions_annual = (
            self.model.solution["carbon_emissions_annual"].loc[last_year].item()
        )
        self.energy_system.carbon_emissions_cumulative_existing = (
            carbon_emissions_cumulative
            + carbon_emissions_annual * (interval_between_years - 1)
        )

    def initialize_component(
        self,
        calling_class,
        component_name,
        index_names=None,
        set_time_steps=None,
        capacity_types=False,
    ):
        """Initialize a modeling component by extracting the stored input data.

        Args:
            calling_class: class from where the method is called
            component_name: name of modeling component
            index_names: names of index sets, only if calling_class is not EnergySystem
            set_time_steps: time steps, only if calling_class is EnergySystem
            capacity_types: boolean if extracted for capacities
            component_data: data to initialize the component
        """
        # if calling class is EnergySystem
        if calling_class == EnergySystem:
            component = getattr(self.energy_system, component_name)
            dict_of_units = {}
            if component_name in self.energy_system.units:
                dict_of_units = self.energy_system.units[component_name]
            if index_names is not None:
                index_list = index_names
            elif set_time_steps is not None:
                index_list = [set_time_steps]
            else:
                index_list = []
            if set_time_steps:
                component_data = component[self.sets[set_time_steps]]
            elif type(component) is float:
                component_data = component
            else:
                component_data = component.squeeze()
        else:
            if index_names is None:
                raise ValueError(f"Index names for {component_name} not specified")
            custom_set, index_list = calling_class.create_custom_set(index_names, self)
            component_data, dict_of_units, attribute_is_series = (
                self.get_attribute_of_all_elements(
                    calling_class,
                    component_name,
                    capacity_types=capacity_types,
                    return_attribute_is_series=True,
                )
            )
            if np.size(custom_set):
                if attribute_is_series:
                    component_data = pd.concat(
                        component_data, keys=component_data.keys()
                    )
                else:
                    component_data = pd.Series(component_data)
                component_data = self.check_for_subindex(component_data, custom_set)
        if isinstance(component_data, pd.Series) and not isinstance(
            component_data.index, pd.MultiIndex
        ):
            component_data.index = pd.MultiIndex.from_product(
                [component_data.index.to_list()]
            )
        return component_data, index_list, dict_of_units

    def check_for_subindex(self, component_data, custom_set):
        """Check if the custom_set can be a subindex of component_data.

        returns subindexed component_data.

        :param component_data: extracted data as pd.Series
        :param custom_set: custom set as subindex of component_data
        :return: component_data: extracted subindexed data as pd.Series
        """
        # if custom_set is subindex of component_data, return subset of component_data
        try:
            if len(component_data) == len(custom_set) and len(custom_set[0]) == len(
                component_data.index[0]
            ):
                return component_data
            else:
                return component_data[custom_set]
        # else delete trivial index levels (that have a single value) and try again
        except Exception:
            _custom_index = pd.Index(custom_set)
            _reduced_custom_index = _custom_index.copy()
            for _level, _shape in enumerate(_custom_index.levshape):
                if _shape == 1:
                    _reduced_custom_index = _reduced_custom_index.droplevel(_level)
            try:
                component_data = component_data[_reduced_custom_index]
                component_data.index = _custom_index
                return component_data
            except KeyError as err:
                raise KeyError(
                    f"the custom set {custom_set} cannot be used as a subindex of"
                    f"{component_data.index}"
                ) from err
