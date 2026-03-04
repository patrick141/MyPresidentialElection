"""
Main file
"""

from src.election import Election

e1 = Election("2020")

DEM = "Democratic"
GOP = "Republican"
OTHER = "Other"

# Updated method name: findStateByName -> find_state_by_name
ARI = e1.find_state_by_name("Arizona")
GA = e1.find_state_by_name("Georgia")
NV = e1.find_state_by_name("Nevada")
NC = e1.find_state_by_name("North Carolina")
MI = e1.find_state_by_name("Michigan")
WI = e1.find_state_by_name("Wisconsin")
PA = e1.find_state_by_name("Pennsylvania")

e1.visualize()

e1.visualize_with_margin_slider()

# Updated method names:
print(e1.get_tipping_point_state())
print(e1.get_popular_vote_margin())
print(e1.get_ec_bias())
print("---")

print(NC.get_winner())
print(NC.get_margin())
print(NC.get_results())

# OLD: e1.applyVoteShiftToState(NC, DEM, 75000)
# NEW: apply vote boost to ONE STATE (turnout boost)
NC.apply_margin_shift_to_party(DEM, 5)
e1.determine_winner()
print("--- after apply margin shift")


print(NC.get_winner())
print(NC.get_margin())
print(NC.get_results())

print("---")

print(e1.get_popular_vote_margin())
print(e1.get_tipping_point_state())
print(e1.get_ec_bias())