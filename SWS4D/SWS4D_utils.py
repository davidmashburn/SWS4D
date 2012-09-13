#!/usr/bin/env python
'''Utility functions for SWS4D'''
import numpy as np
import coo_utils

def ScrubCellID(sws4D,sh,cellID):
    '''Super-slow value clear...'''
    for i in range(sh[0]):
        for j in range(sh[1]):
            for k in range(sh[2]):
                for l in range(sh[3]):
                    if sws4d.seedLil[i][j][k,l] == cellID:
                        sws4d.seedLil[i][j][k,l] = 0

def CopySeedRegionsToAllFrames(sws4d,valsToCopy,t=0,z=0):
    '''This is a function to map one or more seed region (by id) in one frame (default 0,0) to all other frames. Most useful in defining a background region.'''
    regions = [ (coo_utils.CooHDToArray(sws4d.seedLil[t][z])==i) for i in valsToCopy]
    whs = [np.where(i) for i in regions]
    for i in range(sws4d.arr.shape[0]):
        for j in range(sws4d.arr.shape[1]):
            a = coo_utils.CooHDToArray(sws4d.seedLil[i][j])
            for k,v in enumerate(ValsToCopy):
                a[whs[k]] = v
            sws4d.seedLil[i][j] = coo_utils.ArrayToCooHD(a)
