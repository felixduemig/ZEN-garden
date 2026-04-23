from zen_garden.runner import run

opt = run(config="./config.json", dataset="5_multiple_time_steps_per_year")
grb = opt.model.solver_model # das ist gurobipy.Model

print(grb.NumVars, grb.NumConstrs, grb.Runtime, grb.Status)
grb.write("my_model.lp")
