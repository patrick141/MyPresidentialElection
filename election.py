#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  5 21:29:39 2021

@author: pamaro
"""
import pandas as pd
import re

from state import State

class Election():
    def __init__(self, year):
        self.states = []
        self.year = year
        self.results = {}
        self.minEVNeeded = 270
        self.winner = None
        self.df = None
        self.readElectionData(year)

    def readElectionData(self, year):
        self.df = pd.read_csv('data/' + year +  '.csv')
        for index, row in self.df.iterrows():
            name = row['State']
            ev = int(row['EV'])
            s1 = State(name, ev)
            
            myDict = {}
            dem = 'Democratic'
            gop = 'Republican'
            other = 'Other'
            myDict[dem] = row[dem]
            myDict[gop] = row[gop]
            myDict[other] = row[other]
            
            s1.setResults(myDict)
            self.states.append(s1)
        self.determineWinner()
    
    def determineWinner(self):
        demVote = gopVote = 0
        demEV = gopEV = 0
        DEM = "Democratic"
        GOP = "Republican"
        for state in self.states:
            results = state.getResults()
            if state.getWinner() == DEM:
                demEV += state.getEV()
            elif state.getWinner() == GOP:
                gopEV += state.getEV()
            else:
                print("Cannot understand input")
            if re.findall('[0-9]+', state.getName()):
                continue
            demVote += results[DEM]
            gopVote += results[GOP]
        print(demVote)
        print(gopVote)
        if demVote > gopVote:
            self.winner = DEM
        elif gopVote < demVote:
            self.winner = GOP
        else:
            self.winner = "TIED"
        self.results[DEM] = demVote, demEV
        self.results[GOP] = gopVote, gopEV
    
    def sortAlphabetically(self):
        self.states.sort(key=lambda x: x.getName())
    
    def sortByStateMargins(self):
        winParty = self.winner
        otherParty = State.getOtherParty(winParty)
        winnerList = [state for state in self.states if state.getWinner() == winParty]
        winnerList.sort(key=lambda x:x.getMargin()[1])
        otherList = [state for state in self.states if state.getWinner() == otherParty]
        otherList.sort(key=lambda x:x.getMargin()[1])
        newStatesList = winnerList[::-1] + otherList
        self.states = newStatesList
    
    def findStateByName(self, stateName):
        for state in self.states:
            if state.getName() == stateName:
                return state
    
    def getResultOfStateName(self, pStateName):
        pState = self.findStateByName(pStateName)
        if not pState:
            print("State " + pStateName + " not found")
            return
        return self.getResultOfState(pState)
    
    def getResultOfState(self, rState):
        if not isinstance(rState, State):
            print(str(rState) + " not a State class")
            return 
        for state in self.states:
            if state == rState:
                return state.getResults()
        print("State results of " + + "not found")
    
    def printStatesSummary(self):
        for state in self.states:
            print(str(state) + " Winner: "  + state.getWinner())
            
    
    def printStateMargins(self):
        for state in self.states:
            print(str(state) + " Winner: "  + str(state.getMargin()))
    
    def getRelativetoPVMargin(self, mState):
        winParty, winMargin = self.getPopularVoteMargin()
        mStateParty, mStateMargin = mState.getMargin()
        oParty = State.getOtherParty(winParty)
        relState = ""
        relMargin = 0
        if winParty == mStateParty:
            relMargin = winMargin - mStateMargin
            relState = winParty if relMargin < 0.0 else oParty
        else:
            relMargin = winMargin + mStateMargin
            relState = oParty
        return (relState, abs(relMargin))
        
    
    def getTippingPointState(self):
        self.sortByStateMargins()
        evCount = 0
        for state in self.states:
            evCount += state.getEV()
            if evCount > self.minEVNeeded:
                return state
        
    
    def getPopularVoteMargin(self):
        winParty = self.winner
        loserParty = State.getOtherParty(winParty)
        margin = (self.results[winParty][0] - self.results[loserParty][0] )* 100 / self.getTotalVotes()
        return (winParty, margin)
    
    def getTotalVotes(self):
        return sum(state.getTotalVote() for state in self.states)
    
    def getECBias(self):
        tpState = self.getTippingPointState()
        return self.getRelativetoPVMargin(tpState)
    
    def getStatesAsList(self):
        return self.states
    
    def compareStates(state1, state2):
        s1P, s1M = state1.getMargin()
        s1P, s1M = state2.getMargin()

    
    
    
