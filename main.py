"""
Main Class file
"""

from election import Election

e1 = Election('2020')
DEM = "Democratic"
GOP = "Republican"
Other = "Other"
ARI = e1.findStateByName("Arizona")
GA = e1.findStateByName("Georgia")
NV = e1.findStateByName("Nevada")
NC = e1.findStateByName("North Carolina")
MI = e1.findStateByName("Michigan")
WI = e1.findStateByName("Wisconsin")
PA = e1.findStateByName("Pennsylvania")

e1.printSummary()
e1.printStateMargins()
print(e1.getTippingPointState())
print(e1.getECBias())
print("---")
e1.applyVoteShiftToState(NC, DEM, 75000)
print(NC.getWinner())
print(NC.getMargin())
print(NC.getResults())
print("---")
print(e1.getTippingPointState())
print(e1.getECBias())

e1.visualize()