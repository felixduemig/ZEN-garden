"""Check what the capex override actually writes for the FAIL cases."""
import os, sys, json
import pandas as pd

sys.path.insert(0, 'c:/Users/felix/Documents/GitHub/ZEN-garden')
os.chdir('c:/Users/felix/Documents/GitHub/ZEN-garden')

DATASET = '5_multiple_extended_countries'

from rc_capex_file_override import read_capex, _reference_years, _nodes, capex_file_override

# System info
s = json.load(open(f'{DATASET}/system.json'))
ref_year = int(s.get('reference_year', 0))
interval = int(s.get('interval_between_years', 1)) or 1
n_years = int(s.get('optimized_years', 1))
print(f"system.json: ref_year={ref_year}, interval={interval}, n_years={n_years}")
years = [ref_year + i * interval for i in range(n_years)]
print(f"years: {years}")
print(f"_reference_years: {_reference_years(DATASET)}")
print(f"_nodes: {_nodes(DATASET)}")
print()

# Read CAPEX for heat_pump IT at each year
for yi in range(n_years):
    yr = ref_year + yi * interval
    c = read_capex(DATASET, 'heat_pump', 'IT', yr)
    print(f"heat_pump IT year={yr} (yidx={yi}): capex={c}")
print()

# Simulate what override value would be for IT y1 (ratio=0.8415, MARGIN=0.10)
MARGIN = 0.10
yr1 = ref_year + 1 * interval
c_IT_y1 = read_capex(DATASET, 'heat_pump', 'IT', yr1)
ratio_IT_y1 = 0.8415
override_build = c_IT_y1 * (1 - (1 + MARGIN) * ratio_IT_y1)
print(f"IT y1 override (build): capex {c_IT_y1} -> {override_build:.4f}")
print(f"  (ratio={(1-(1+MARGIN)*ratio_IT_y1)*100:.2f}% of original)")

# Simulate for ES y0 (PASS case)
yr0 = ref_year + 0 * interval
c_ES_y0 = read_capex(DATASET, 'heat_pump', 'ES', yr0)
ratio_ES_y0 = 0.4015
override_build_ES = c_ES_y0 * (1 - (1 + MARGIN) * ratio_ES_y0)
print(f"\nES y0 override (build): capex {c_ES_y0} -> {override_build_ES:.4f}")
print(f"  (ratio={(1-(1+MARGIN)*ratio_ES_y0)*100:.2f}% of original)")
print()

# Check what CSV gets written for a mock override of IT y1
print("=== Mock-Override for IT y1: would write this CSV ===")
from rc_capex_file_override import _capex_meta, _build_grid
meta = _capex_meta(DATASET, 'heat_pump', None)
folder, akey, path = meta
nodes = _nodes(DATASET)
ref_years = _reference_years(DATASET)
cells = {('IT', yr1): override_build}
df = _build_grid(folder, akey, path, cells, nodes, ref_years)
print(df.to_string())
