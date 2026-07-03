.. _plugins.available_events:

Available events
====================

.. _plugins.available_events.after_construct_params:

Event ``after_construct_params``
------------------------------------

The event ``after_construct_params`` is triggered once, after all parameters of all
element classes have been constructed, but before any variables or constraints are
built. The ``optimization_setup`` object is passed to the event handler. This is the
place to overwrite parameter values before they are consumed by the variable and
constraint construction. The trigger is placed in ``element.py``:

.. code-block:: python

    # construct Params
    cls.construct_params(optimization_setup)
    EventPublisher.trigger(
        Event.after_construct_params, optimization_setup=optimization_setup
    )
    # construct Vars
    cls.construct_vars(optimization_setup)

Exemplary use cases for this event include:

- Overwriting individual parameter values (e.g. a fixed technology attribute) before
  they enter cost terms or constraint bounds. You have access to
  ``optimization_setup.parameters``, ``optimization_setup.sets``, and
  ``optimization_setup.system``.

.. _plugins.available_events.after_model_construction:

Event ``after_model_construction``
------------------------------------

The event ``after_model_construction`` is triggered after model construction, but before scaling and solving the model:
The ``optimization_setup`` object is passed to the event handler, so you are able to modify the optimization problem
before scaling and solving. The trigger is placed in ``runner.py``:

.. code-block:: python

    # create optimization problem
    optimization_setup.construct_optimization_problem()
    EventPublisher.trigger(
        Event.after_model_construction, optimization_setup=optimization_setup
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

Exemplary use cases for this event include:

- Define new variables to be used in new constraints. Refer to the documentation
  :ref:`here <adding_elements.adding_variables>`
- Define new constraints (see documentation :ref:`here <adding_elements.adding_constraints>`),
  e.g. policy targets for certain capacity expansions or generation constraints of
  technologies. You have access to all preexisting sets, parameters, and variables.
- Defining a new objective function. You can first delete the already defined objective function
  with ``optimization_setup.model.remove_objective()`` and then add a new one. For instance, you can
  think of adding a bias term to the objective function, which co-optimizes cost and another metric.

.. note::
    At the moment, you cannot define new sets and parameters through plugins, as you would need to read
    new input data, which is currently not supported.

.. _plugins.available_events.after_postprocessing:

Event ``after_postprocessing``
------------------------------------

The event ``after_postprocessing`` is triggered once results have been written to
disk for the current scenario and horizon step. Both the ``optimization_setup``
object and the ``postprocess`` object (an instance of ``Postprocess``, whose
``name_dir`` attribute holds the output directory of this scenario/step) are passed
to the event handler. The trigger is placed in ``runner.py``:

.. code-block:: python

    # write results
    postprocess = Postprocess(
        optimization_setup,
        scenarios=config.scenarios,
        subfolder=subfolder,
        model_name=model_name,
        scenario_name=scenario_name,
        param_map=param_map,
    )
    EventPublisher.trigger(
        Event.after_postprocessing,
        optimization_setup=optimization_setup,
        postprocess=postprocess,
    )

Exemplary use cases for this event include:

- Deriving and writing additional, plugin-specific result files from the solved
  model (e.g. reading live constraint duals from ``optimization_setup.model``) into
  ``postprocess.name_dir``, next to the standard ZEN-garden output files.
