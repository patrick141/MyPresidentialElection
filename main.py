"""
Main file
"""

from src.election import Election, visualize_multi_year_slider

e2020 = Election("2020")
e2024 = Election("2024")

DEM = "Democratic"
GOP = "Republican"
OTHER = "Other"

# Static map for 2024
e2024.visualize()

# Multi-year interactive map with year toggle (2020 / 2024)
visualize_multi_year_slider([e2020, e2024])

# Analytics for 2024
NC = e2024.find_state_by_name("North Carolina")

print(e2024.get_tipping_point_state())
print(e2024.get_popular_vote_margin())
print(e2024.get_ec_bias())
print("---")

print(NC.get_winner())
print(NC.get_margin())
print(NC.get_results())

NC.apply_margin_shift_to_party(DEM, 5)
e2024.determine_winner()
print("--- after apply margin shift")

print(NC.get_winner())
print(NC.get_margin())
print(NC.get_results())

print("---")

print(e2024.get_popular_vote_margin())
print(e2024.get_tipping_point_state())
print(e2024.get_ec_bias())
