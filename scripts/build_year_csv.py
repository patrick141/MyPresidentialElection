"""
build_year_csv.py: Normalize a MIT Election Lab CSV into the project's data schema.

Usage:
    python scripts/build_year_csv.py <year> [--mit <path>] [--out <path>]

Arguments:
    year          Election year to extract (e.g. 2016)
    --mit PATH    Path to the MIT 1976-2020 CSV  (default: data/1976-2020-president.csv)
    --out PATH    Output path                     (default: data/<year>.csv)

Output format (matches data/2020.csv):
    State, EV, Democratic, Republican, Other

ME/NE districts (ME-1, ME-2, NE-1, NE-2, NE-3) are written with correct EV values
but zero vote counts — fill in manually or leave for a future pipeline step.

EV note: values are derived from the 2012.csv file (2010 census, verified) and
extrapolated from known apportionment changes for earlier census periods.
Spot-check totals against https://www.archives.gov/electoral-college/allocation
before publishing results.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Electoral College allocations by census period
# Source for 2010 census: derived from data/2012.csv (verified in-project)
# Source for 2000/1990 census: derived from known apportionment changes
# ---------------------------------------------------------------------------

# 2010 census → elections 2012, 2016, 2020
_EV_2010 = {
    "Alabama": 9, "Alaska": 3, "Arizona": 11, "Arkansas": 6,
    "California": 55, "Colorado": 9, "Connecticut": 7, "Delaware": 3,
    "District of Columbia": 3, "Florida": 29, "Georgia": 16, "Hawaii": 4,
    "Idaho": 4, "Illinois": 20, "Indiana": 11, "Iowa": 6, "Kansas": 6,
    "Kentucky": 8, "Louisiana": 8, "Maine": 2, "Maryland": 10,
    "Massachusetts": 11, "Michigan": 16, "Minnesota": 10, "Mississippi": 6,
    "Missouri": 10, "Montana": 3, "Nebraska": 2, "Nevada": 6,
    "New Hampshire": 4, "New Jersey": 14, "New Mexico": 5, "New York": 29,
    "North Carolina": 15, "North Dakota": 3, "Ohio": 18, "Oklahoma": 7,
    "Oregon": 7, "Pennsylvania": 20, "Rhode Island": 4, "South Carolina": 9,
    "South Dakota": 3, "Tennessee": 11, "Texas": 38, "Utah": 6, "Vermont": 3,
    "Virginia": 13, "Washington": 12, "West Virginia": 5, "Wisconsin": 10,
    "Wyoming": 3,
}

# 2000 census → elections 2004, 2008
# Derived from _EV_2010 by reversing the 2000→2010 apportionment shift.
_EV_2000 = {**_EV_2010, **{
    "Arizona": 10, "Florida": 27, "Georgia": 15, "Illinois": 21,
    "Iowa": 7, "Louisiana": 9, "Massachusetts": 12, "Michigan": 17,
    "Missouri": 11, "Nevada": 5, "New Jersey": 15, "New York": 31,
    "Ohio": 20, "Pennsylvania": 21, "South Carolina": 8, "Texas": 34,
    "Utah": 5, "Washington": 11,
}}

# 1990 census → election 2000
# Derived from _EV_2000 by reversing the 1990→2000 apportionment shift.
_EV_1990 = {**_EV_2000, **{
    "Arizona": 8, "California": 54, "Colorado": 8, "Connecticut": 8,
    "Florida": 25, "Georgia": 13, "Illinois": 22, "Indiana": 12,
    "Michigan": 18, "Mississippi": 7, "Nevada": 4, "New York": 33,
    "North Carolina": 14, "Ohio": 21, "Oklahoma": 8, "Pennsylvania": 23,
    "Texas": 32, "Wisconsin": 11,
}}

# District rows inserted immediately after their parent state.
# EV values are constant across all census periods (1 each).
_DISTRICTS = {
    "Maine": [("ME-1", 1), ("ME-2", 1)],
    "Nebraska": [("NE-1", 1), ("NE-2", 1), ("NE-3", 1)],
}


def _ev_table(year: int) -> dict:
    if year <= 2000:
        return _EV_1990
    if year <= 2008:
        return _EV_2000
    return _EV_2010


def _normalize_state_name(raw: str) -> str:
    """Convert MIT all-caps state name to title-case, fixing known edge cases."""
    name = raw.strip().title()
    # str.title() capitalises 'Of' — keep it lowercase to match project schema
    name = name.replace(" Of ", " of ")
    return name


def build(mit_path: Path, year: int, out_path: Path) -> None:
    df = pd.read_csv(mit_path)

    required = {"year", "state", "party_simplified", "candidatevotes", "candidate"}
    missing = required - set(df.columns)
    if missing:
        print(f"ERROR: MIT CSV is missing columns: {missing}", file=sys.stderr)
        sys.exit(1)

    df = df[df["year"] == year].copy()
    if df.empty:
        print(f"ERROR: No rows found for year {year}.", file=sys.stderr)
        sys.exit(1)

    # Drop blank-vote placeholder rows (no real candidate) before aggregating.
    df = df[~df["candidate"].str.strip().isin(["BLANK VOTES", ""])]

    # Bucket parties: DEMOCRAT → Democratic, REPUBLICAN → Republican, rest → Other
    def _bucket(party: str) -> str:
        if party == "DEMOCRAT":
            return "Democratic"
        if party == "REPUBLICAN":
            return "Republican"
        return "Other"

    df["party_bucket"] = df["party_simplified"].apply(_bucket)

    # Aggregate votes per state × party bucket
    agg = (
        df.groupby(["state", "party_bucket"])["candidatevotes"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ("Democratic", "Republican", "Other"):
        if col not in agg.columns:
            agg[col] = 0

    agg["State"] = agg["state"].apply(_normalize_state_name)

    ev_map = _ev_table(year)
    agg["EV"] = agg["State"].map(ev_map)

    unmapped = agg[agg["EV"].isna()]["State"].tolist()
    if unmapped:
        print(
            f"WARNING: No EV mapping found for: {unmapped}. "
            "Check _EV_* tables in this script.",
            file=sys.stderr,
        )

    agg["EV"] = agg["EV"].fillna(0).astype(int)

    # Build sorted output: alphabetical by state, districts injected after parent.
    rows = agg[["State", "EV", "Democratic", "Republican", "Other"]].to_dict("records")
    rows.sort(key=lambda r: r["State"])

    output = []
    for row in rows:
        output.append(row)
        if row["State"] in _DISTRICTS:
            for dist_name, dist_ev in _DISTRICTS[row["State"]]:
                output.append({
                    "State": dist_name,
                    "EV": dist_ev,
                    "Democratic": 0,
                    "Republican": 0,
                    "Other": 0,
                })

    out_df = pd.DataFrame(output, columns=["State", "EV", "Democratic", "Republican", "Other"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    print(f"Wrote {len(out_df)} rows → {out_path}")

    total_ev = out_df["EV"].sum()
    if total_ev != 538:
        print(
            f"WARNING: EV total is {total_ev}, expected 538. "
            "Verify the EV table for this census period.",
            file=sys.stderr,
        )
    else:
        print(f"EV total: {total_ev} ✓")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, help="Election year (e.g. 2016)")
    parser.add_argument(
        "--mit",
        default="data/1976-2020-president.csv",
        help="Path to MIT election CSV (default: data/1976-2020-president.csv)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path (default: data/<year>.csv)",
    )
    args = parser.parse_args()

    valid_years = {1976, 1980, 1984, 1988, 1992, 1996, 2000, 2004, 2008, 2012, 2016, 2020}
    if args.year not in valid_years:
        print(
            f"ERROR: {args.year} is not a presidential election year covered by the MIT dataset.",
            file=sys.stderr,
        )
        sys.exit(1)

    mit_path = Path(args.mit)
    if not mit_path.exists():
        print(f"ERROR: MIT CSV not found at {mit_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out) if args.out else Path(f"data/{args.year}.csv")
    build(mit_path, args.year, out_path)


if __name__ == "__main__":
    main()
