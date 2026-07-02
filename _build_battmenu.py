"""Build a dataset variant with a MENU of fixed-duration batteries (battery_2h/4h/8h)
replacing the single free-e2p battery. Canonical dataset stays untouched."""
import json, os, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "6_showcase_countries")
DST = os.path.join(BASE, "6_showcase_countries_battmenu")
DURATIONS = [2, 4, 8]

if os.path.exists(DST):
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)

stor = os.path.join(DST, "set_technologies", "set_storage_technologies")
batt = os.path.join(stor, "battery")
for D in DURATIONS:
    dst = os.path.join(stor, f"battery_{D}h")
    shutil.copytree(batt, dst)
    aj = os.path.join(dst, "attributes.json")
    a = json.load(open(aj))
    a["energy_to_power_ratio_min"]["default_value"] = float(D)
    a["energy_to_power_ratio_max"]["default_value"] = float(D)
    json.dump(a, open(aj, "w"), indent=2)
shutil.rmtree(batt)   # replace the single battery with the menu

sj = os.path.join(DST, "system.json")
s = json.load(open(sj))
s["set_storage_technologies"] = [f"battery_{D}h" for D in DURATIONS]
json.dump(s, open(sj, "w"), indent=2)

print("built", DST)
print("storage techs:", s["set_storage_technologies"])
for D in DURATIONS:
    a = json.load(open(os.path.join(stor, f"battery_{D}h", "attributes.json")))
    print(f"  battery_{D}h e2p min/max =",
          a["energy_to_power_ratio_min"]["default_value"],
          a["energy_to_power_ratio_max"]["default_value"])
