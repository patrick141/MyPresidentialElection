#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  5 21:29:39 2021

@author: pamaro
"""
import pandas as pd
import re
import plotly.express as px
import plotly.graph_objects as go


from state import State
from constants import us_state_to_abbrev

class Election():
    def __init__(self, year):
        self.states = []
        self.year = year
        self.results = {}
        self.minEVNeeded = 270
        self.totalVote = 0
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
        Other = "Other"
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
            self.totalVote += state.getTotalVote()
        if demVote > gopVote:
            self.winner = DEM
        elif gopVote < demVote:
            self.winner = GOP
        else:
            self.winner = "TIED"
        self.results[DEM] = demVote, demEV
        self.results[GOP] = gopVote, gopEV
        self.results[Other] = self.totalVote - (demVote + gopVote)
    
    def printSummary(self):
        winner = self.winner
        print(winner, " won the election")      
    
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
            print(str(state) + " | Winner: "  + state.getWinner())
            
    
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
        return self.totalVote
    
    def getECBias(self):
        tpState = self.getTippingPointState()
        return self.getRelativetoPVMargin(tpState)
    
    def getStatesAsList(self):
        return self.states
    
    def getStatesWonByParty(self, party):
        return [state for state in self.states if state.getWinner() == party]
        
    
    def compareStates(state1, state2):
        s1P, s1M = state1.getMargin()
        s2P, s2M = state2.getMargin()
        
    def getStrongestStateByParty(self, party):
        self.sortByStateMargins()
        return self.states[0] if self.states[0].getWinner() == party else self.states[-1]
    
    def applyPercentageShiftToState(self, pState, sParty, sMargin):
        pStateParty, pStateMargin = pState.getMargin()
        oParty = State.getOtherParty(sParty)
        rState = ""
        rMargin = 0
        if sParty == pStateParty:
            rMargin = pStateMargin + sMargin
            rState = sParty
        return (rState, abs(rMargin))
     
    def applyVoteShiftToState(self, state, party, vote):
        state.applyVoteShift(party, vote)
    
    def adjust_state_margins(self, margin_shift):
        for state in self.states:
            # Assume each state has a method to adjust its margin
            self.applyVoteShiftToState(state, "Dem", margin_shift * 10000)
        
    
    def visualize(self):
        state_summary = [
            {"State": state.getName(), "Winner": state.getWinner(), "Votes": state.getVoteByParty(state.getWinner())} 
            for state in self.states
        ]
        df = pd.DataFrame(state_summary)
        df['State Abbr'] = df['State'].map(us_state_to_abbrev)
        
        color_map = {
            'Democratic': 'blue',
            'Republican': 'red'
        }
        
        fig = px.choropleth(
            df,
            locations='State Abbr',
            locationmode='USA-states',
            color='Winner',
            color_discrete_map=color_map,
            hover_name='State',
            hover_data={'Winner': True, 'Votes': ':,', 'State Abbr': False},
            scope="usa",
            title=self.year + ' US Election Results'
        )

        fig.update_layout(
            geo=dict(
                lakecolor='rgb(255, 255, 255)'
            ),
        )

        fig.show()
        fig.write_html("election_results_map.html")
        