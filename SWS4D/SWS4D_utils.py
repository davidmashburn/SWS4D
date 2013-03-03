#!/usr/bin/env python
'''Utility functions for SWS4D'''
import os,glob
import numpy as np
import wx
import coo_utils
import scipy.sparse
import GifTiffLoader as GTL
import SeedWaterSegmenter as SWS

def GetFileBasenameForSaveLoad(f=None,saveDialog=False):
    '''Try to return a proper base name for SWS4D files (strip extensions, etc)
       If no file is given, use a file selection dialog (or a save dialog) to get one'''
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
    for i in ['_waterDiff','_seeds','_maskSeeds','_maskDiff']:
        if f[-len(i):]==i:
            f = f[:-len(i)]
    return f

def GetMostRecentSegmentationBasename(segmentationDir):
    '''Load the most recent segmentation from a folder'''
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
    
    try:
        _,maskSeedLil = coo_utils.LoadRCDFileToCooHD(f+'_maskSeeds',tolil=True)
        _,maskLilDiff = coo_utils.LoadRCDFileToCooHD(f+'_maskDiff',tolil=True)
        
        return (seedLil,waterLilDiff),(maskSeedLil,maskLilDiff)
    except IOError:
        return (seedLil,waterLilDiff),None

def ScrubCellID(sws4D,sh,cellID):
    '''Super-slow value clear...'''
    for i in range(sh[0]):
        for j in range(sh[1]):
            for k in range(sh[2]):
                for l in range(sh[3]):
                    if sws4D.seedLil[i][j][k,l] == cellID:
                        sws4D.seedLil[i][j][k,l] = 0

def CopySeedRegionsToAllFrames(sws4d,valsToCopy,t=0,z=0):
    '''This is a function to map one or more seed region (by id) in one frame (default 0,0) to all other frames. Most useful in defining a background region.'''
    regions = [ (coo_utils.CooHDToArray(sws4d.seedLil[t][z])==i) for i in valsToCopy]
    whs = [np.where(i) for i in regions]
    for i in range(sws4d.shape[0]):
        for j in range(sws4d.shape[1]):
            a = coo_utils.CooHDToArray(sws4d.seedLil[i][j])
            for k,v in enumerate(valsToCopy):
                a[whs[k]] = v
            sws4d.seedLil[i][j] = coo_utils.ArrayToCooHD(a)

def LoadSWS_as_sLwLD(d):
    '''Load a Seeds.py and Segments folder and convert them to seedLil and waterLilDiff
       Loading code adapted from SWS.WatershedData.Open'''
    segmentsD = os.path.join(d,'Segments')
    seedPointsFile = os.path.join(d,'Seeds.py')
    waterArr = GTL.LoadFileSequence(segmentsD,'Segment*')
    Seeds = SWS.LoadSeedPointsFile(seedPointsFile)
    
    assert len(Seeds.seedList)==len(Seeds.seedVals), 'Corrupt Seeds.py file! seedList and seedVals must be the same length!!!'
    assert len(Seeds.seedList)>=len(waterArr), 'Seeds.py file must have at least as many frames as Segments directory!'
    
    shape = len(Seeds.seedList),waterArr.shape[1:] # get the shape of the whole dataset
    
    # Build the waterLilDiff and pad it to be the same size as seedLil (below)
    waterLilDiff = coo_utils.ArrayToCooDiff(waterArr,dtype=np.uint16,tolil=True)
    numEmptyFrames = len(Seeds.seedList)-len(waterArr)
    for i in range(numEmptyFrames):
        waterLilDiff.append(coo_utils.ArrayToCooDiff(0*waterArr[0],dtype=np.uint16,tolil=True))
    
    seedLil = [None]*shape[0]
    for i in range(shape[0]):
        if (( None in [Seeds.seedList[i],Seeds.seedVals[i]] ) or
            ( [] in [Seeds.seedList[i],Seeds.seedVals[i]] )):
            seedLil[i] = scipy.sparse.lil_matrix(shape[1:], dtype=np.uint16)
        else:
            row,col = np.array(Seeds.seedList[i]).T
            vals = Seeds.seedVals[i]
            seedLil[i] = scipy.sparse.coo_matrix((vals,(row,col)), shape=shape[1:], dtype=np.uint16).tolil()
    
    return [seedLil],[waterLilDiff],[1]+shape # convert from xyz to xyzt with one time point
    
def ConvertSWSToSWS4D(d,outputBaseName=None):
    '''Convert a Seeds.py and Segments folder to seedLil and waterLilDiff files
       Uses LoadSWS_as_sLwLD'''
    outputBaseName = GetFileBasenameForSaveLoad(outputBaseName,saveDialog=True)
    
    seedLil,waterLilDiff,shape = LoadSWS_as_sLwLD(d)
    
    coo_utils.SaveCooHDToRCDFile(waterLilDiff,shape,outputBaseName+'_waterDiff',fromlil=True)
    coo_utils.SaveCooHDToRCDFile(seedLil,shape,outputBaseName+'_seeds',fromlil=True)

def SaveToSWS(seedLil,waterLilDiff,d):
    '''Save a seedLil and a waterLilDiff with a single time point to the SWS3D format:
           a directory "d" with a Seeds.py file and a Segments directory
       Saving code adapted from SWS.WatershedData.Save'''
    assert len(seedLil)==len(waterLilDiff)==1, 'seedLil and waterLilDiff MUST have only one time point or conversion to 3D is not possible'
    
    print 'Saving To ',d
    if not os.path.exists(d):
        os.mkdir(d)
    
    segmentsD = os.path.join(d,'Segments')
    if not os.path.exists(segmentsD):
        os.mkdir(segmentsD)
    
    segmentsBase = os.path.join(segmentsD,'Segment')
    seedPointsFile = os.path.join(d,'Seeds.py')
    
    waterArr = coo_utils.CooDiffToArray(waterLilDiff[0],dtype=np.uint16) # not ideal to make the whole array, but this should be ok for this use case
    nonEmptyFrames = [ i for i in range(len(waterArr)) if len(np.where(waterArr[i])[0])>0 ] # get a list of non-empty frames for the watershed
    GTL.SaveFileSequence(waterArr,basename=segmentsBase,format='tif',sparseSave=nonEmptyFrames)
    
    # Still just want an easy format to save and load...
    cooList = [  ( None if i==None else i.tocoo() )  for i in seedLil[0]  ]
    seedList = [  ( None if i==None else np.array([i.row,i.col]).T.tolist())  for i in cooList  ]
    seedVals = [  ( None if i==None else i.data.astype(np.int).tolist() ) for i in cooList  ]
    
    walgorithm = ['PyMorph']*len(seedList)
    woundCenters = [None]*len(seedList)
    SWS.WriteSeedPointsFile(seedPointsFile,seedList,seedVals,walgorithm,woundCenters)
    
    for i,s in enumerate(seedLil):
        if s==None:
            print i,'--'
        elif s.nnz==0:
            print 'Empty!'
        else:
            print i,'initialized'

def ConvertSWS4DToSWS(baseName,outputDir):
    '''Convert seedLil and waterLilDiff files with a single time point to the SWS3D format:
           a directory "d" with a Seeds.py file and a Segments directory
       Uses SaveToSWS'''
    baseName = GetFileBasenameForSaveLoad(baseName,saveDialog=False)
    
    shapeWD = coo_utils.GetShapeFromFile( baseName+'_waterDiff' )
    shapeS = coo_utils.GetShapeFromFile( baseName+'_seeds' )
    assert shapeWD == shapeS, 'Shapes of SWS4D files do not match!'
    
    _, waterLilDiff = coo_utils.LoadRCDFileToCooHD(baseName+'_waterDiff',tolil=True)
    _, seedLil = coo_utils.LoadRCDFileToCooHD(baseName+'_seeds',tolil=True)
    
    SaveToSWS(seedLil,waterLilDiff,outputDir)
