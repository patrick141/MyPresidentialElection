"""
Placeholder script, will be implemented as a stretch goal in Phase 3.
"""
import sys
import os
from pathlib import Path

SUPPORTED_YEARS = ("2020", "2024")

if __name__ == "__main__":
    year = sys.argv[1] if len(sys.argv) > 1 else None

    if year not in SUPPORTED_YEARS:
        print(f"Usage: python scripts/build_year_csv.py <year>")
        print(f"Supported years: {', '.join(SUPPORTED_YEARS)}")
        sys.exit(1)

    print(f"[placeholder] build_year_csv.py — Script not built yet")
    print(f"Requested year: {year}")
    print(f"Next step implement code")
