#!/usr/bin/env python
'''Utility functions for SWS4D'''

def ScrubCellID(sws4D,sh,cellID):
    '''Super-slow value clear...'''
    for i in range(sh[0]):
        for j in range(sh[1]):
            for k in range(sh[2]):
                for l in range(sh[3]):
                    if sws4d.seedLil[i][j][k,l] == cellID:
                        sws4d.seedLil[i][j][k,l] = 0

