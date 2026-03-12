"""
Main entry point: instantiates Election objects and launches the interactive map.

USAGE
-----
Uncomment exactly ONE block in the "Run" section below, then:
    python main.py
"""

from src.model.election import Election
from src.model.constants import DEM, GOP
from src.visualization.visualize import visualize_multi_year_slider, visualize_comparison

# ---------------------------------------------------------------------------
# Load election years
# ---------------------------------------------------------------------------
e2004 = Election("2004")
e2008 = Election("2008")
e2012 = Election("2012")
e2016 = Election("2016")
e2020 = Election("2020")
e2024 = Election("2024")

# ---------------------------------------------------------------------------
# Run — uncomment ONE block
# ---------------------------------------------------------------------------

# Standard multi-year interactive map (year toggle + margin slider)
visualize_multi_year_slider([e2020, e2024])

# All six cycles
# visualize_multi_year_slider([e2004, e2008, e2012, e2016, e2020, e2024])

# Synthetic cross-year matchup: 2008 Dem coalition vs 2004 GOP coalition
# synthetic = Election.combine_party_results(e2008, DEM, e2004, GOP,
#                                            label="2008 Dem vs 2004 GOP")
# visualize_multi_year_slider([synthetic])

# Synthetic cross-year matchup: 2020 Dem coalition vs 2024 GOP coalition
# synthetic = Election.combine_party_results(e2020, DEM, e2024, GOP,
#                                            label="2020 Dem vs 2024 GOP")
# visualize_multi_year_slider([synthetic])

# Side-by-side comparison (two static maps)
# visualize_comparison(e2020, e2024, output_file="comparison_2020_vs_2024.html")
# synthetic = Election.combine_party_results(e2020, DEM, e2024, GOP,
#                                            label="2020 Dem vs 2024 GOP")
# visualize_comparison(synthetic, e2024, output_file="comparison_synthetic_vs_2024.html")

# ---------------------------------------------------------------------------
# Scenario Export — uncomment any line to write CSV/JSON
# ---------------------------------------------------------------------------
# e2024.export_scenario("scenarios/2024_baseline.csv")
# e2024.apply_margin_swing_all_states(DEM, 5)
# e2024.export_scenario("scenarios/2024_D+5.csv")
# e2024.reset_all_states()
# e2024.apply_margin_swing_all_states(GOP, 5)
# e2024.export_scenario("scenarios/2024_R+5.csv")
# e2024.reset_all_states()
