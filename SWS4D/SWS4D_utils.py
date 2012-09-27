#!/usr/bin/env python
'''Utility functions for SWS4D'''
import os,glob
import numpy as np
import wx
import coo_utils

def GetFileBasenameForSaveLoad(f=None,saveDialog=False):
    if f==None:
        # Use a dialog to choose the file, use overwrite prompt when saving...
        flags = ( wx.ID_SAVE|wx.FD_OVERWRITE_PROMPT if saveDialog else wx.ID_OPEN)
        loadMessage = "Load Seeds... (choose a *_nnzs.npy, *_rcd.npy, or *_shape.txt)"
        message = ( 'Save Seeds as...' if saveDialog else loadMessage )
        
        f = wx.FileSelector(message,flags=flags)
        
        if f in [None,u'','']: # dialog was cancelled
            print 'Cancelled'
            return None
    
    # Strip off extensions if present on the file
    for i in ['_nnzs.npy','_rcd.npy','_shape.txt']:
        if f[-len(i):]==i:
            f = f[:-len(i)]
    for i in ['_waterDiff','_seeds']:
        if f[-len(i):]==i:
            f = f[:-len(i)]
    return f

def GetMostRecentSegmentationBasename(segmentationDir):
    g=glob.glob(os.path.join(segmentationDir,'*.npy'))
    gmax,gmTime = g[0],0
    for i in g:
        mt = os.path.getmtime(i)
        if mt>gmTime:
            gmax,gmTime = i,mt
    print gmax
    
    return GetFileBasenameForSaveLoad(gmax)

def LoadMostRecentSegmentation(segmentationDir):
    '''Load the most recent segmentation'''
    f = GetMostRecentSegmentationBasename(segmentationDir)
    
    # No shape checking, just load the data
    _, seedLil = coo_utils.LoadRCDFileToCooHD(f+'_seeds',tolil=True)
    _, waterLilDiff = coo_utils.LoadRCDFileToCooHD(f+'_waterDiff',tolil=True)
    
    return seedLil,waterLilDiff

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
    for i in range(sws4d.shape[0]):
        for j in range(sws4d.shape[1]):
            a = coo_utils.CooHDToArray(sws4d.seedLil[i][j])
            for k,v in enumerate(ValsToCopy):
                a[whs[k]] = v
            sws4d.seedLil[i][j] = coo_utils.ArrayToCooHD(a)
