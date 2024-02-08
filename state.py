#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  5 21:29:39 2021

@author: pamaro
"""


class State():
    def __init__(self, name, EV):
        self.__name = name
        self.__EV = EV
        self.__results = {}
        self.__winner = None
        
    def getName(self):
        return self.__name
    
    def setName(self, name):
        self.__name = name
    
    def getEV(self):
        return self.__EV
    
    def setEV(self, newEV):
        self.__EV = newEV
    
    def getResults(self):
        return self.__results
    
    def setResults(self, pResults):
        self.__results = pResults
        self.determineWinner()
    
    def determineWinner(self):
        demVote = self.__results['Democratic']
        gopVote = self.__results['Republican']
        if demVote > gopVote:
            self.__winner = 'Democratic'
        elif demVote < gopVote:
            self.__winner = 'Republican'
        else:
            self.__winner = 'TIED'
        
    def printSummary(self):
        print(self)
        print(self.__results)
        
    def printResult(self):
        pass
        

    def getTotalVote(self):
        return sum(self.__results.values())
    
    def getVoteByParty(self, party):
        if party in self.__results:
            return self.__results[party]
    
    def getVotePerByParty(self, party):
        return (self.getVoteByParty(party) / self.getTotalVote()) * 100
    
    def getWinner(self):
        return self.__winner 
    
    def setWinner(self, pWinner):
        self.__winner = pWinner
    
    @staticmethod
    def getOtherParty(oParty):
        if oParty == "Democratic":
            return "Republican"
        elif oParty == "Republican":
            return "Democratic"
        else:
            return "Do not understand: " + oParty
    
    def getMargin(self):
        votePer = self.getVotePerByParty(self.__winner)
        otherParty = self.getOtherParty(self.__winner)
        otherPer = self.getVotePerByParty(otherParty)
        return (self.__winner, votePer - otherPer)
    
    def applyVoteShift(self, party, shiftVotes):
        newResults = self.__results;
        if party in newResults:
            newResults[party] += shiftVotes
            self.setResults(newResults)
        else:
            print("Party not in result");
        
    
    def __str__(self):
        return self.__name +  " " + str(self.__EV) + " EV"