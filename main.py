"""
Main entry point — instantiates Election objects and launches the interactive map.
"""

from src.model.election import Election
from src.visualization.visualize import visualize_multi_year_slider

# Party name aliases used throughout simulation calls
DEM = "Democratic"
GOP = "Republican"
OTHER = "Other"

# Load 2020 and 2024 election data from data/YEAR.csv
e2008 = Election("2008")
e2012 = Election("2012")
e2016 = Election("2016")
e2020 = Election("2020")
e2024 = Election("2024")

# --- Scenario Export (uncomment any block below to generate CSV/JSON files) ---
# e2024.export_scenario("scenarios/2024_baseline.csv")
# e2024.export_scenario("scenarios/2024_baseline.json")

# D+5 national swing — uncomment to export
# e2024.apply_margin_swing_all_states(DEM, 5)
# e2024.export_scenario("scenarios/2024_D+5.csv")
# e2024.export_scenario("scenarios/2024_D+5.json")
# e2024.reset_all_states()

# R+5 national swing — uncomment to export
# e2024.apply_margin_swing_all_states(GOP, 5)
# e2024.export_scenario("scenarios/2024_R+5.csv")
# e2024.export_scenario("scenarios/2024_R+5.json")
# e2024.reset_all_states()

# Build and open the multi-year interactive map with year toggle (2020 / 2024)
visualize_multi_year_slider([e2008, e2012, e2016, e2020, e2024])
