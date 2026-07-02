"""Generate a MINIMAL ZEN-garden dataset that reproduces the CB scarcity-vertex
over-statement of the operational RC via a transmission bottleneck — the same
mechanism as nuclear@ES (import-islanded node).  Maps toy_lp3 1:1:

  toy_lp3                         ->  this dataset
  G1 cheap, AT CAP   (cost 10)    ->  import over the congested line from MAIN (cost 10)
  G2 expensive       (cost 50)    ->  local 'peaker' at ISL (cost 50)
  C  cheapest        (cost 5)     ->  candidate 'baseload' at ISL (cost 5), unbuilt

No TSA (4 unaggregated steps) so every number is hand-traceable.  ISL is fed only
through one line of capacity 30.  In the scarce step ISL demand >= 30, so the line is
congested and the peaker sets the price (50).  But a finite build of 'baseload'
displaces the cheap IMPORT (10), not the peaker -> its realized value (10-5=5/unit) is
far below the price-based reconstruction (50-5=45/unit): a 9x over-statement, and the
+-1% re-solve barely builds.

Tunables via env: ISL_SCARCE_DEMAND (step-0 demand), ISL_BASELOAD_CAPEX.
"""
import os, json, csv, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
DS   = os.path.join(os.path.dirname(BASE), "rc_scarcity_demo")
SCARCE_DEMAND  = float(os.environ.get("ISL_SCARCE_DEMAND", "30.0"))
BASELOAD_CAPEX = float(os.environ.get("ISL_BASELOAD_CAPEX", "3000"))


def wjson(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), indent=2)


def wcsv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def conv(name, opex_var, capex, lifetime=40, ofix=0.0):
    return {
        "capacity_addition_min": {"default_value": 0.0, "unit": "GW"},
        "capacity_addition_max": {"default_value": "inf", "unit": "GW"},
        "capacity_addition_unbounded": {"default_value": 0.0, "unit": "GW"},
        "capacity_existing": {"default_value": 0.0, "unit": "GW"},
        "capacity_limit": {"default_value": "inf", "unit": "GW"},
        "min_load": {"default_value": 0.0, "unit": "1"},
        "max_load": {"default_value": 1.0, "unit": "1"},
        "lifetime": {"default_value": lifetime, "unit": "1"},
        "opex_specific_variable": {"default_value": opex_var, "unit": "Euro/MWh"},
        "opex_specific_fixed": {"default_value": ofix, "unit": "Euro/kW"},
        "reference_carrier": {"default_value": ["electricity"]},
        "input_carrier": {"default_value": ["fuel"]},
        "output_carrier": {"default_value": ["electricity"]},
        "conversion_factor": {"fuel": {"default_value": 1.0, "unit": "GWh/GWh"}},
        "carbon_intensity_technology": {"default_value": 0.0, "unit": "kilotons/GWh"},
        "construction_time": {"default_value": 0.0, "unit": "1"},
        "capacity_investment_existing": {"default_value": 0.0, "unit": "GW"},
        "max_diffusion_rate": {"default_value": "inf", "unit": "1"},
        "capex_specific_conversion": {"default_value": capex, "unit": "Euro/kW"},
    }


def build():
    if os.path.exists(DS):
        shutil.rmtree(DS)
    wjson(os.path.join(DS, "system.json"), {
        "set_conversion_technologies": ["cheap_gen", "peaker", "baseload"],
        "set_storage_technologies": [],
        "set_transport_technologies": ["power_line"],
        "set_nodes": ["MAIN", "ISL"],
        "reference_year": 2025,
        "unaggregated_time_steps_per_year": 4,
        "aggregated_time_steps_per_year": 4,
        "conduct_time_series_aggregation": False,
        "optimized_years": 1,
        "interval_between_years": 1,
        "use_rolling_horizon": False,
    })
    es = os.path.join(DS, "energy_system")
    wjson(os.path.join(es, "attributes.json"), {
        "carbon_emissions_annual_limit": {"default_value": "inf", "unit": "gigatons"},
        "carbon_emissions_budget": {"default_value": "inf", "unit": "gigatons"},
        "carbon_emissions_cumulative_existing": {"default_value": 0.0, "unit": "gigatons"},
        "price_carbon_emissions": {"default_value": 0.0, "unit": "Euro/tons"},
        "price_carbon_emissions_budget_overshoot": {"default_value": 0.0, "unit": "Euro/tons"},
        "price_carbon_emissions_annual_overshoot": {"default_value": "inf", "unit": "Euro/tons"},
        "knowledge_depreciation_rate": {"default_value": 0.1, "unit": "1"},
        "knowledge_spillover_rate": {"default_value": 0.025, "unit": "1"},
        "market_share_unbounded": {"default_value": 0.1, "unit": "1"},
        "discount_rate": {"default_value": 0.05, "unit": "1"},
    })
    wjson(os.path.join(es, "base_units.json"), {"unit": ["hour", "GW", "km", "megatons", "megaEuro"]})
    open(os.path.join(es, "unit_definitions.txt"), "w", encoding="utf-8").write(
        "Euro = [currency] = EURO = Eur\n")
    wcsv(os.path.join(es, "set_nodes.csv"), ["node", "lon", "lat"],
         [["MAIN", 10.0, 50.0], ["ISL", 12.0, 41.0]])
    wcsv(os.path.join(es, "set_edges.csv"), ["edge", "node_from", "node_to"],
         [["MAIN-ISL", "MAIN", "ISL"], ["ISL-MAIN", "ISL", "MAIN"]])

    el = os.path.join(DS, "set_carriers", "electricity")
    wjson(os.path.join(el, "attributes.json"), {
        "carbon_intensity_carrier_import": {"default_value": 0.0, "unit": "kilotons/GWh"},
        "carbon_intensity_carrier_export": {"default_value": 0.0, "unit": "kilotons/GWh"},
        "demand": {"default_value": 0.0, "unit": "GW"},
        "price_shed_demand": {"default_value": 3000.0, "unit": "Euro/MWh"},
        "availability_import": {"default_value": 0.0, "unit": "GW"},
        "availability_export": {"default_value": 0.0, "unit": "GW"},
        "availability_import_yearly": {"default_value": "inf", "unit": "GWh"},
        "availability_export_yearly": {"default_value": "inf", "unit": "GWh"},
        "price_export": {"default_value": 0.0, "unit": "kiloEuro/GWh"},
        "price_import": {"default_value": 0.0, "unit": "kiloEuro/GWh"},
    })
    wcsv(os.path.join(el, "demand.csv"), ["time", "MAIN", "ISL"],
         [[0, 0.0, SCARCE_DEMAND], [1, 0.0, 12.0], [2, 0.0, 12.0], [3, 0.0, 12.0]])

    fu = os.path.join(DS, "set_carriers", "fuel")
    wjson(os.path.join(fu, "attributes.json"), {
        "carbon_intensity_carrier_import": {"default_value": 0.0, "unit": "kilotons/GWh"},
        "carbon_intensity_carrier_export": {"default_value": 0.0, "unit": "kilotons/GWh"},
        "demand": {"default_value": 0.0, "unit": "GW"},
        "price_shed_demand": {"default_value": "inf", "unit": "Euro/MWh"},
        "availability_import": {"default_value": "inf", "unit": "GW"},
        "availability_export": {"default_value": 0.0, "unit": "GW"},
        "availability_import_yearly": {"default_value": "inf", "unit": "GWh"},
        "availability_export_yearly": {"default_value": "inf", "unit": "GWh"},
        "price_export": {"default_value": 0.0, "unit": "kiloEuro/GWh"},
        "price_import": {"default_value": 0.0, "unit": "kiloEuro/GWh"},
    })

    ct = os.path.join(DS, "set_technologies", "set_conversion_technologies")
    wjson(os.path.join(ct, "cheap_gen", "attributes.json"), conv("cheap_gen", 10.0, 99999, 40))
    wcsv(os.path.join(ct, "cheap_gen", "capacity_existing.csv"),
         ["node", "year_construction", "capacity_existing"], [["MAIN", 2020, 100.0]])
    wcsv(os.path.join(ct, "cheap_gen", "capacity_limit.csv"),
         ["node", "capacity_limit"], [["MAIN", 100.0], ["ISL", 0.0]])

    wjson(os.path.join(ct, "peaker", "attributes.json"), conv("peaker", 50.0, 99999, 40))
    wcsv(os.path.join(ct, "peaker", "capacity_existing.csv"),
         ["node", "year_construction", "capacity_existing"], [["ISL", 2020, 50.0]])
    wcsv(os.path.join(ct, "peaker", "capacity_limit.csv"),
         ["node", "capacity_limit"], [["MAIN", 0.0], ["ISL", 50.0]])

    wjson(os.path.join(ct, "baseload", "attributes.json"), conv("baseload", 5.0, BASELOAD_CAPEX, 40))
    wcsv(os.path.join(ct, "baseload", "capacity_limit.csv"),
         ["node", "capacity_limit"], [["MAIN", 0.0], ["ISL", 100.0]])

    tt = os.path.join(DS, "set_technologies", "set_transport_technologies", "power_line")
    wjson(os.path.join(tt, "attributes.json"), {
        "capacity_addition_min": {"default_value": 0.0, "unit": "GW"},
        "capacity_addition_max": {"default_value": 0.0, "unit": "GW"},
        "capacity_addition_unbounded": {"default_value": 0.0, "unit": "GW"},
        "capacity_existing": {"default_value": 0.0, "unit": "GW"},
        "capacity_limit": {"default_value": "inf", "unit": "GW"},
        "min_load": {"default_value": 0.0, "unit": "1"},
        "max_load": {"default_value": 1.0, "unit": "1"},
        "lifetime": {"default_value": 60, "unit": "1"},
        "opex_specific_variable": {"default_value": 0.0, "unit": "kiloEuro/GWh"},
        "reference_carrier": {"default_value": ["electricity"]},
        "carbon_intensity_technology": {"default_value": 0.0, "unit": "kilotons/GWh/km"},
        "construction_time": {"default_value": 0.0, "unit": "1"},
        "capacity_investment_existing": {"default_value": 0.0, "unit": "GW"},
        "opex_specific_fixed": {"default_value": 0.0, "unit": "Euro/MW"},
        "max_diffusion_rate": {"default_value": "inf", "unit": "1"},
        "transport_loss_factor_linear": {"default_value": 0.0, "unit": "1/km"},
        "capex_per_distance_transport": {"default_value": 999999.0, "unit": "Euro/km/MW"},
        "distance": {"default_value": "inf", "unit": "km"},
    })
    wcsv(os.path.join(tt, "capacity_existing.csv"),
         ["edge", "year_construction", "capacity_existing"],
         [["MAIN-ISL", 2020, 30.0], ["ISL-MAIN", 2020, 30.0]])
    wcsv(os.path.join(tt, "capacity_limit.csv"),
         ["edge", "capacity_limit"], [["MAIN-ISL", 30.0], ["ISL-MAIN", 30.0]])
    wcsv(os.path.join(tt, "distance.csv"),
         ["edge", "distance"], [["MAIN-ISL", 100.0], ["ISL-MAIN", 100.0]])
    os.makedirs(os.path.join(DS, "set_technologies", "set_storage_technologies"), exist_ok=True)
    return DS


if __name__ == "__main__":
    build()
    print("dataset written to", DS, "| SCARCE_DEMAND", SCARCE_DEMAND, "| BASELOAD_CAPEX", BASELOAD_CAPEX)
