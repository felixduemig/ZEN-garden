"""Quick dataset structure validator — wraps ZEN-models/data_structure_test.py."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ZEN-models"))
from data_structure_test import validate_dataset

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASETS = [
    "5_multiple_time_steps_per_year",
    "5_multiple_extended",
]

for ds in DATASETS:
    try:
        ok = validate_dataset(path=BASE_DIR, dataset_name=ds)
        status = "OK" if ok else "empty"
    except (ValueError, AssertionError) as e:
        status = f"FAIL: {e}"
    print(f"  {ds:45s}  {status}")