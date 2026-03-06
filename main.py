"""
Main file
"""

from src.election import Election
from src.visualize import visualize_multi_year_slider

DEM = "Democratic"
GOP = "Republican"
OTHER = "Other"

e2020 = Election("2020")
#e2020.apply_margin_swing_to_state("Minnesota", GOP, 10)
#e2020.determine_winner()

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

# Multi-year interactive map with year toggle (2020 / 2024)
visualize_multi_year_slider([e2020, e2024])
