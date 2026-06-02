"""
build_cb_greenfield_2050.py
===========================
Creates a single-year greenfield snapshot of the full Crystal Ball model at 2050.

What it does:
  1. Copies Crystal Ball -> 7_cb_greenfield_2050
  2. system.json: sets optimized_years=1 (single-year snapshot)
  3. Zeros all capacity_existing.csv files         (greenfield: no legacy stock)
  4. Zeros all capacity_investment_existing.csv files

Note: diffusion limit is disabled at code level
(constraint_technology_diffusion_limit commented out in technology.py),
so no patching of max_diffusion_rate is needed.

Run once to create the dataset, then point main_rc_simplex.py to "greenfield".
"""

import json
import os
import shutil
import csv
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE      = Path(__file__).parent
SRC       = BASE / "ZEN-models" / "data" / "Crystal_Ball"
DST       = BASE / "7_cb_greenfield_2050"

assert SRC.exists(), f"Source not found: {SRC}"

# ── 1. Copy dataset ───────────────────────────────────────────────────────────
if DST.exists():
    print(f"Removing existing {DST.name} ...")
    shutil.rmtree(DST)

print(f"Copying {SRC.name} -> {DST.name} ...")
shutil.copytree(SRC, DST)
print(f"  Done ({sum(1 for _ in DST.rglob('*'))} files copied)")

# ── 2. Patch system.json ──────────────────────────────────────────────────────
sys_path = DST / "system.json"
with open(sys_path) as f:
    system = json.load(f)

system["optimized_years"] = 1       # single-year snapshot
# keep reference_year = 2050, aggregated_time_steps_per_year = 10
# keep all nodes and technologies

with open(sys_path, "w") as f:
    json.dump(system, f, indent=2)

print(f"\nsystem.json patched:")
print(f"  optimized_years = 1  (was {system.get('optimized_years', '?')} -> now 1)")
print(f"  reference_year  = {system['reference_year']}")
print(f"  nodes           = {len(system['set_nodes'])}")
print(f"  time_steps/year = {system.get('aggregated_time_steps_per_year', system.get('unaggregated_time_steps_per_year', '?'))}")

# ── 3. Zero capacity_existing.csv ────────────────────────────────────────────
def zero_capacity_csv(csv_path: Path):
    """Read a capacity_existing.csv and write back with all numeric values = 0."""
    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        return  # empty or header-only, skip

    header = rows[0]
    # Find numeric columns (all except typically 'node', 'year_construction', 'edge')
    numeric_cols = []
    for i, col in enumerate(header):
        col_lower = col.strip().lower()
        if col_lower not in ("node", "edge", "year_construction", "year", "time"):
            try:
                float(rows[1][i])
                numeric_cols.append(i)
            except (ValueError, IndexError):
                pass

    new_rows = [header]
    for row in rows[1:]:
        new_row = list(row)
        for i in numeric_cols:
            if i < len(new_row):
                new_row[i] = "0"
        new_rows.append(new_row)

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

zeroed_existing = 0
zeroed_inv_existing = 0

for csv_path in DST.rglob("capacity_existing.csv"):
    zero_capacity_csv(csv_path)
    zeroed_existing += 1

for csv_path in DST.rglob("capacity_investment_existing.csv"):
    zero_capacity_csv(csv_path)
    zeroed_inv_existing += 1

print(f"\nGreenfied zeroing:")
print(f"  capacity_existing.csv           zeroed: {zeroed_existing} files")
print(f"  capacity_investment_existing.csv zeroed: {zeroed_inv_existing} files")

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"""
{'='*60}
Greenfield 2050 snapshot created: {DST.name}
{'='*60}
  Source:          {SRC}
  Destination:     {DST}
  Years:           1 (2050 only)
  Nodes:           {len(system['set_nodes'])}
  Technologies:    {len(system.get('set_conversion_technologies', []))} conversion
                   {len(system.get('set_storage_technologies', []))} storage
                   {len(system.get('set_transport_technologies', []))} transport
  Greenfield:      capacity_existing = 0 for all technologies
  Diffusion:       disabled at code level (constraint commented out)

Next step: in main_rc_simplex.py, set
  DATASET = DATASETS["greenfield"]

and add to DATASETS dict:
  "greenfield": "7_cb_greenfield_2050",
""")
