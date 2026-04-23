import math

import pyomo.environ as pyo


def solve_case(scale: float) -> dict:
    model = pyo.ConcreteModel()

    model.x = pyo.Var(domain=pyo.NonNegativeReals)
    model.y = pyo.Var(domain=pyo.NonNegativeReals)

    model.obj = pyo.Objective(
        expr=100 * scale * model.x + 50 * scale * model.y,
        sense=pyo.maximize,
    )
    model.con = pyo.Constraint(expr=model.x + model.y <= 1000 * scale)

    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    model.rc = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    solver = pyo.SolverFactory("gurobi_direct")
    result = solver.solve(model, tee=False)

    return {
        "termination": str(result.solver.termination_condition),
        "x": pyo.value(model.x),
        "y": pyo.value(model.y),
        "dual_con": model.dual[model.con],
        "rc_x": model.rc[model.x],
        "rc_y": model.rc[model.y],
    }


def main() -> None:
    base = solve_case(scale=1.0)
    sf = 1e-3
    scaled = solve_case(scale=sf)

    # Rescale to compare both formulations in the same units.
    scaled_rescaled = {
        "x": scaled["x"] / sf,
        "y": scaled["y"] / sf,
        "dual_con": scaled["dual_con"] / sf,
        "rc_x": scaled["rc_x"] / sf,
        "rc_y": scaled["rc_y"] / sf,
    }

    print("Base model:")
    print(base)
    print("\nScaled model (rescaled back):")
    print(scaled_rescaled)

    checks = {
        "x": math.isclose(base["x"], scaled_rescaled["x"], rel_tol=1e-8, abs_tol=1e-8),
        "y": math.isclose(base["y"], scaled_rescaled["y"], rel_tol=1e-8, abs_tol=1e-8),
        "dual_con": math.isclose(base["dual_con"], scaled_rescaled["dual_con"], rel_tol=1e-8, abs_tol=1e-8),
        "rc_x": math.isclose(base["rc_x"], scaled_rescaled["rc_x"], rel_tol=1e-8, abs_tol=1e-8),
        "rc_y": math.isclose(base["rc_y"], scaled_rescaled["rc_y"], rel_tol=1e-8, abs_tol=1e-8),
    }

    print("\nConsistency checks:")
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")

    if not all(checks.values()):
        raise SystemExit("At least one reduced-cost/dual consistency check failed.")


if __name__ == "__main__":
    main()
