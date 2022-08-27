#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  5 21:29:39 2021

@author: pamaro
"""

from election import Election

e1 = Election('2020')
DEM = "Democratic"
GOP = "Republican"
Other = "Other"
ARI = e1.findStateByName("Arizona")
GA = e1.findStateByName("Georgia")
NV = e1.findStateByName("Nevada")
MI = e1.findStateByName("Michigan")
WI = e1.findStateByName("Wisconsin")
PA = e1.findStateByName("Pennsylvania")

e1.printSummary()
e1.printStateMargins()
print(e1.getTippingPointState())
print(e1.getECBias())

e1.sortByStateMargins();
print(e1.states);
e1.printStateMargins()