#!/usr/bin/env python
import os,glob
import numpy as np
import scipy.ndimage
import scipy.sparse

import wx

from traits.api import HasTraits, Int, Range, String, Float, Bool, Enum, Instance, Property, Array, List, Dict, Button, on_trait_change, NO_COMPARE
from traitsui.api import View, Item, Group, RangeEditor, VGroup, HGroup, VSplit, HSplit, NullEditor
from mayavi.core.api import PipelineBase
from mayavi.core.ui.api import MayaviScene, SceneEditor, MlabSceneModel

from mayavi import mlab
from tvtk.api import tvtk

import mahotas

#import np_utils
#reload(np_utils)
from np_utils import BresenhamFunction,BresenhamTriangle,circs,shprs
import coo_utils

import mlabArrayViewer_LoadAsNeeded
reload(mlabArrayViewer_LoadAsNeeded)
from mlabArrayViewer_LoadAsNeeded import ArrayViewVolume,ArrayView4D,ArrayView4DVminVmax,ArrayView4DDual
from SWS4D_utils import GetFileBasenameForSaveLoad,LoadMostRecentSegmentation

mouseInteractionModes = ['print','doodle','erase','line','plane','move']

# Compressed and LoadAsNeeded...
class SeedWaterSegmenter4D(ArrayView4DVminVmax):
    # store the full waterArr and seedArr as cooHD's (actually lil_matrix format) instead
    #seedArr_t = Array(shape=[None]*3)
    waterArr_t = Array(shape=[None]*3) # This makes motion through time much slower, but that's ok
    
    sceneWater = Instance(MlabSceneModel, ())
    
    numPlots=Int(3)
    numCursors=Int(2)
    displayString=String('')
    
    overlayOpacity=Range(low=0.0, high=1.0, value=1.0)
    
    nextSeedValue = Range(low=0, high=10000, value=2, exclude_high=False, mode='spinner')
    #mouseInteraction = String('move')
    mouseInteraction=Enum(mouseInteractionModes)
    watershedButton = Button('Run Watershed')
    #updateSeedArr_tButton = Button('UpdateSeedArr_t')
    useTissueSeg = Bool(False)
    volumeRenderButton = Button('VolumeRender')
    saveButton = Button('Save')
    loadButton = Button('Load')
    
    tempButton = Button('Temp')
    
    view = View(VGroup(
            Item('displayString', label=' ', style='readonly'),
            HGroup(
             Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=600, width=600, show_label=False),
             Item('sceneWater', editor=SceneEditor(scene_class=MayaviScene), height=600, width=600, show_label=False),
            ),
            Group('xindex','yindex','zindex','tindex','vmin','vmax','overlayOpacity','xybutton','mouseInteraction',
             HGroup('watershedButton','nextSeedValue','useTissueSeg','volumeRenderButton'),#'updateSeedArr_tButton'),
             HGroup('saveButton','loadButton','tempButton')
            )
           ), resizable=True,title='SeedWaterSegmenter 4D')
    
    def __init__(self,listOfTiffStackFiles,cursorSize=2,loadfile=None,sigma=1,vmin=0,vmax=2**16-1,**traits):
        HasTraits.__init__(self,listOfTiffStackFiles=listOfTiffStackFiles, **traits) # Call __init__ on the super
        #self.listOfTiffStackFiles = listOfTiffStackFiles
        self.vmin = vmin
        self.vmax = vmax
        self.sigma=sigma
        
        self.oldTindex = None
        self.updateArr()
        self.initPlotsAndCursors()
        
        # Only really store the waterLilDiffs (see coo_utils for conversions to array)
        # This is NOT the same thing as the SWS3D woutline...
        self.ClearSeedsAndWatershed()
        self.ClearMask()
        
        self.waterArr_t = np.zeros(self.shape[1:],dtype=np.int32) # just one stack for LoadAsNeeded
        #self.seedArr_t = np.zeros(self.shape[1:],dtype=np.int32)
        
        #self.useSeedArr_t=False
        
        if loadfile!=None:
            self.Load(loadfile)
        
        self.lastPos=None
        self.lastPos2=None
    def ClearSeedsAndWatershed(self):
        '''Initialize seeds and watershed to empty lil_matrices'''
        self.seedLil = [ [ scipy.sparse.lil_matrix(self.shape[2:],dtype=np.uint16)
                          for j in range(self.shape[1]) ]
                        for i in range(self.shape[0]) ]
        self.waterLilDiff = [ [ scipy.sparse.lil_matrix(self.shape[2:],dtype=np.int32) # This needs to be able to go negative...
                               for j in range(self.shape[1]) ]
                             for i in range(self.shape[0]) ]
    def ClearMask(self):
        '''Initialize mask seeds and watershed to empty lil_matrices'''
        self.maskSeedLil = [ [ scipy.sparse.lil_matrix(self.shape[2:],dtype=np.uint16)
                              for j in range(self.shape[1]) ]
                            for i in range(self.shape[0]) ]
        self.maskLilDiff = [ [ scipy.sparse.lil_matrix(self.shape[2:],dtype=np.uint16)
                              for j in range(self.shape[1]) ]
                            for i in range(self.shape[0]) ]
    def SetMapPlotColormap(self,plots,clearBG=False):
        '''Secret sauce to display the map plot and make it look like SWS'''
        from SeedWaterSegmenter.SeedWaterSegmenter import GetMapPlotRandomArray
        mapPlotCmap = np.zeros([4,10000],np.int)
        mapPlotCmap[:3] = GetMapPlotRandomArray()
        mapPlotCmap[3] = 255
        if clearBG:
            mapPlotCmap[3,0] = 0
        for i in ['XY','XZ','YZ']:
            plots[i].module_manager.scalar_lut_manager.lut.table = mapPlotCmap.T
            plots[i].ipw.reslice_interpolate = 'nearest'
            plots[i].parent.scalar_lut_manager.data_range = 0,10000
    def AddMouseInteraction(self,plots):
        # the heart of the mouse interactions
        for view in ['XY','XZ','YZ']:
            def genMC(view):
                def mouseClick(obj, evt):
                    seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
                    position = obj.GetCurrentCursorPosition()
                    # pos = map(int,position); pos[2] = self.zindex
                    if view=='XY':
                        pos = [self.tindex,self.zindex,int(position[0]),int(position[1])]
                    elif view=='XZ':
                        pos = [self.tindex,int(position[0]),self.yindex,int(position[1])]
                    elif view=='YZ':
                        pos = [self.tindex,int(position[1]),int(position[0]),self.xindex]
                    
                    if self.mouseInteraction not in mouseInteractionModes:
                        print 'ERROR! UNSUPPORTED MODE!'
                        return
                    elif self.mouseInteraction=='print':
                        print position,pos
                    elif self.mouseInteraction=='move':
                        print self.mouseInteraction,position,pos
                        self.tindex,self.zindex,self.yindex,self.xindex = pos
                    elif self.mouseInteraction in ['doodle','line','plane']:
                        print self.mouseInteraction,position,pos
                        seedLil[pos[0]][pos[1]][pos[2],pos[3]] = self.nextSeedValue
                        #self.seedArr_t[pos[1],pos[2],pos[3]] = self.nextSeedValue
                        #self.plots['XY'].mlab_source.scalars[pos[0],pos[1]] = self.nextSeedValue
                        
                        if self.lastPos!=None:
                            if self.mouseInteraction == 'line':
                                points = BresenhamFunction(pos,self.lastPos)
                            elif self.mouseInteraction == 'plane':
                                points = BresenhamTriangle(pos,self.lastPos,self.lastPos2)
                            else:
                                points=[]
                            
                            pointsExp = []
                            for p in points:
                                #if 0<=p[2]<self.shape[1]-1 and 0<=p[0]<self.shape[2]-1 and 0<=p[1]<self.shape[3]-1:
                                if 0<=p[0]<self.shape[0] and 0<=p[1]<self.shape[1] and 0<=p[2]<self.shape[2]-1 and 0<=p[2]<self.shape[2]-1:
                                    for i in range(2):
                                        for j in range(2):
                                            #for k in range(2): # Lose the z fiddle... too confusing
                                                #points.append((p[0]+i,p[1]+j,p[2]+k))
                                                pointsExp.append((p[0],p[1],p[2]+i,p[3]+j))
                            points = np.array(list(set(pointsExp)))
                            
                            #self.seedArr[self.tindex,points[:,2],points[:,0],points[:,1]] = self.nextSeedValue
                            for p in points:
                                seedLil[p[0]][p[1]][p[2],p[3]] = self.nextSeedValue
                                #if p[0]==self.tindex:
                                #    self.seedArr_t[p[1],p[2],p[3]]=self.nextSeedValue
                        
                        if self.mouseInteraction == 'line' and not np.sum(self.lastPos!=pos)==0:
                            self.lastPos = pos
                        elif self.mouseInteraction == 'plane' and not np.sum(self.lastPos!=pos)==0:
                            self.lastPos, self.lastPos2 = pos, self.lastPos
                    
                    elif self.mouseInteraction=='erase': # erase mode
                        print 'Erase',position
                    
                    if self.mouseInteraction!='print':
                        plots[view].mlab_source.scalars = plots[view].mlab_source.scalars
                        #self.update_seeds_overlay()
                        import time
                        ti = time.time()
                        #if self.useSeedArr_t:#hasattr(self,'switch'):
                        #    print 'arr'
                        #    self.update_all_plots(self.seedArr_t,self.plots[1]) 
                        #    #del(self.switch)
                        #else:
                        #    print 'lil'
                        self.update_all_plots(seedLil[self.tindex],self.plots[1])
                        #    #self.switch=None
                        print time.time()-ti
                return mouseClick
            
            plots[view].ipw.add_observer('InteractionEvent', genMC(view))
            plots[view].ipw.add_observer('StartInteractionEvent', genMC(view))
    
    def GetMaskOutlineForWatershed(self):
        '''Get the outline array from the mask '''
        maskArr = coo_utils.CooDiffToArray(self.maskLilDiff[self.tindex])-1 # make background 0 and foreground 1
        maskOutline = scipy.ndimage.binary_dilation(maskArr,iterations=2) - maskArr
        return maskOutline.astype(np.uint16)*(2**16-1)
        
        #OLD -- 
        # Dilate-Erode
        # maskOutline = scipy.ndimage.binary_dilation(maskArr) - scipy.ndimage.binary_erosion(maskArr)
        # Set to second-to-maximum value for uint16 (maximum is used to block watershed which is not what we want)
        
    def RunWatershed(self,index='all'):
        tList = ( range(self.shape[0]) if index=='all' else [index] )
        for t in tList:
            #self.updateSeedArr_t(t)
            seedArr_t = self.getSeedArr_t(t)
            arr = self.arr[t]
            for z in range(self.shape[1]):
                # if there is any masking for this stack, then use it
                # (and otherwise skip it...)
                if not self.useTissueSeg:
                    if self.maskLilDiff[t][z].nnz>0:
                        arr = np.maximum( arr , self.GetMaskOutlineForWatershed() )
                        arr[ np.where(arr==0) ] = 1 # if there are any blocked sites, convert to background...
                        break
            
            self.waterArr_t[:] = mahotas.cwatershed(arr,seedArr_t)
            self.updateWaterLilDiff(t)
            if self.useTissueSeg:
                print 'Whole Tissue',
            print 'Watershed on frame',t
        self.lastPos=None
    @on_trait_change('scene.activated')
    def display_scene(self):
        self.display_scene_helper(self.arr,self.scene,self.plots[0],self.cursors[0])
        self.make_plots(self.arr,self.scene,self.plots[1],zeroFill=True)
        for plots in self.plots[:2]:
            for s in ('XY','XZ','YZ'):
                plots[s].mlab_source.scalars = np.array(plots[s].mlab_source.scalars)
        self.AddMouseInteraction(self.plots[0])
        self.SetMapPlotColormap(self.plots[1],clearBG=True)
        
        # Try this instead
        self.contours = {'XY':None,'XZ':None,'YZ':None}
        self.make_plots(self.waterArr_t,self.scene,self.contours,useSurf=True)
        for i in ['XY','XZ','YZ']:
            self.contours[i].enable_contours=True
            self.contours[i].contour.auto_contours=False
            self.contours[i].contour.contours=[0.5]
    @on_trait_change('sceneWater.activated')
    def display_sceneWater(self):
        self.display_scene_helper(self.arr,self.sceneWater,self.plots[2],self.cursors[1],zeroFill=True)
        for plots in self.plots[2:]:
            for s in ('XY','XZ','YZ'):
                plots[s].mlab_source.scalars = np.array(plots[s].mlab_source.scalars)
        self.SetMapPlotColormap(self.plots[2])
        self.AddMouseInteraction(self.plots[2])
    def update_x_plots(self,arr_t,plots):
        if plots is not {}:
            if arr_t.__class__==np.ndarray:
                plots['YZ'].mlab_source.scalars = arr_t[:,:,self.xindex].T
            elif arr_t.__class__== list:
                plots['YZ'].mlab_source.scalars = np.array( [ arr_tz[:,self.xindex].toarray().flatten()
                                                             for arr_tz in arr_t ] ,dtype=np.int32).T
    def update_y_plots(self,arr_t,plots):
        if plots is not {}:
            if arr_t.__class__==np.ndarray:
                plots['XZ'].mlab_source.scalars = arr_t[:,self.yindex,:]
            elif arr_t.__class__== list:
                plots['XZ'].mlab_source.scalars = np.array( [ arr_tz[self.yindex,:].toarray().flatten()
                                                             for arr_tz in arr_t ] ,dtype=np.int32)
    def update_z_plots(self,arr_t,plots):
        if plots is not {}:
            if arr_t.__class__==np.ndarray:
                plots['XY'].mlab_source.scalars = arr_t[self.zindex]
            elif arr_t.__class__== list:
                plots['XY'].mlab_source.scalars = arr_t[self.zindex].toarray().astype(np.int32)
    #def getWaterArr_t_z(self):
    #    # This should be the inner function in updateWaterArr_t
    #    waterLilDiff = (self.waterLilDiff if not self.useTissueSeg else self.maskLilDiff)
    #    return coo_utils.CooDiffToArray( self.waterLilDiff[self.tindex][self.zindex] )
    def updateWaterArr_t_z(self,tindex=None,zindex=None):
        if tindex==None:
            tindex=self.tindex
        if zindex==None:
            zindex=self.zindex
        waterLilDiff = (self.waterLilDiff if not self.useTissueSeg else self.maskLilDiff)
        self.waterArr_t[zindex] = coo_utils.CooDiffToArray( waterLilDiff[tindex][zindex] )
    def updateWaterArr_t(self,tindex=None):
        if tindex==None:
            tindex=self.tindex
        waterLilDiff = (self.waterLilDiff if not self.useTissueSeg else self.maskLilDiff)
        self.waterArr_t[:] = coo_utils.CooDiffToArray( waterLilDiff[tindex] )
    #def updateSeedArr_t(self,tindex=None):
    def getSeedArr_t(self,tindex=None):
        if tindex==None:
            tindex=self.tindex
        seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
        return coo_utils.CooHDToArray( seedLil[tindex], dtype=np.int32)
        #self.useSeedArr_t = True
    def updateWaterLilDiff(self,tindex=None):
        if tindex==None:
            tindex=self.tindex
        waterLilDiff = (self.waterLilDiff if not self.useTissueSeg else self.maskLilDiff)
        waterLilDiff[tindex] = coo_utils.ArrayToCooDiff( self.waterArr_t )
    #def update_seeds_overlay(self):
    #    import time
    #    t=time.time()
    #    self.updateSeedArr_t()
    #    self.update_all_plots(self.seedArr_t,self.plots[1])
    #@on_trait_change('updateSeedArr_tButton')
    #def updateSeedArr_tCallback(self,tindex=None):
    #    self.update_seeds_overlay()
    #    self.updateWaterArr_t()
    #    self.update_all_plots(self.waterArr_t,self.plots[2])
    @on_trait_change('overlayOpacity')
    def overlayOpacityCallback(self):
        for s in ['XY','XZ','YZ']:
            self.plots[1][s].ipw.texture_visibility = (self.overlayOpacity>0)
            self.contours[s].actor.property.opacity = self.overlayOpacity
        for i in ['x','y','zx','zy']:
            self.cursors[0][i].actor.visible = (self.overlayOpacity>0)
            self.cursors[1][i].actor.visible = (self.overlayOpacity>0)
    @on_trait_change('watershedButton')
    def watershedButtonCallback(self):
        self.RunWatershed(index = self.tindex)
        # waterArr_t and seedArr_t are updated in RunWatershed
        seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
        self.update_all_plots(seedLil[self.tindex],self.plots[1])
        self.update_all_plots(self.waterArr_t,self.plots[2])
        self.update_all_contours()
    @on_trait_change('nextSeedValue')
    def nextSeedValue_cb(self):
        '''Three actions:
             Limit potential values to 0,1,2 in tissue mode
             Reset line/plane mousing
             Plot contour for the new value'''
        # adding functionality to reset to 0,1, or 2 if in tissue mode
        if self.useTissueSeg and self.nextSeedValue>2:
            self.nextSeedValue = 2
        self.lastPos = None
        self.update_all_contours()
    @on_trait_change('mouseInteraction')
    def mouseInteractionChanged(self):
        self.lastPos=None
    def contourHelper(self,arr,xyzStr):
        self.contours[xyzStr].mlab_source.scalars = arr.astype(np.int32)
        self.contours[xyzStr].enable_contours=True
        self.contours[xyzStr].contour.auto_contours=False
        self.contours[xyzStr].contour.contours=[0.5]
    def update_x_contours(self):
        arr = (self.waterArr_t[:,:,self.xindex].T==self.nextSeedValue)
        self.contourHelper(arr,'YZ')
    def update_y_contours(self):
        arr = (self.waterArr_t[:,self.yindex]==self.nextSeedValue)
        self.contourHelper(arr,'XZ')
    def update_z_contours(self):
        arr = (self.waterArr_t[self.zindex]==self.nextSeedValue)
        self.contourHelper(arr,'XY')
    def update_all_contours(self):
        self.update_x_contours()
        self.update_y_contours()
        self.update_z_contours()
    @on_trait_change('xindex')
    def update_x_plots_cb(self):
        self.updateArr()
        self.updateWaterArr_t()
        self.update_x_plots(self.arr,self.plots[0])
        #if self.useSeedArr_t:
        #    self.update_x_plots(self.seedArr_t,self.plots[1])
        #else:
        seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
        self.update_x_plots(seedLil[self.tindex],self.plots[1])
        self.update_x_plots(self.waterArr_t,self.plots[2])
        self.update_x_cursors()
        self.update_x_contours()
    @on_trait_change('yindex')
    def update_y_plots_cb(self):
        self.updateArr()
        self.updateWaterArr_t()
        self.update_y_plots(self.arr,self.plots[0])
        #if self.useSeedArr_t:
        #    self.update_y_plots(self.seedArr_t,self.plots[1])
        #else:
        seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
        self.update_y_plots(seedLil[self.tindex],self.plots[1])
        self.update_y_plots(self.waterArr_t,self.plots[2])
        self.update_y_cursors()
        self.update_y_contours()
    @on_trait_change('zindex')
    def update_z_plots_cb(self):
        self.updateZFrame()
        self.updateWaterArr_t_z()
        self.update_z_plots(self.arr,self.plots[0])
        seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
        self.update_z_plots(seedLil[self.tindex],self.plots[1])
        self.update_z_plots(self.waterArr_t,self.plots[2])
        self.update_z_cursors()
        self.update_z_contours()
    @on_trait_change('tindex')
    def update_all_plots_cb(self):
        self.updateZFrame()
        self.updateWaterArr_t_z()

        self.update_z_plots(self.arr,self.plots[0])
        seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
        self.update_z_plots(seedLil[self.tindex],self.plots[1])
        self.update_z_plots(self.waterArr_t,self.plots[2])
        self.update_z_contours()
    @on_trait_change('xybutton')
    def update_arr_and_all_plots(self):
        self.updateArr(force=True)
        self.updateWaterArr_t()
        self.update_all_plots(self.arr,self.plots[0])
        seedLil = (self.seedLil if not self.useTissueSeg else self.maskSeedLil)
        self.update_all_plots(seedLil[self.tindex],self.plots[1])
        self.update_all_plots(self.waterArr_t,self.plots[2])
        self.update_all_contours()
        
    @on_trait_change('useTissueSeg')
    def switch_segmentation_modes(self):
        '''Any time we switch modes, we need to swap out the whole waterArr
        This is a trade-off which maintains fast t-motion while keeping down memory usage'''
        self.updateWaterArr_t()
        self.update_all_plots_cb()
        if self.nextSeedValue>2:
            self.nextSeedValue=2
    
    def Save(self,filename=None):
        print 'Save'
        filename = GetFileBasenameForSaveLoad(filename,saveDialog=True) # Overwrite protection ONLY IF FILENAME IS NONE!
        if filename!=None:
            print 'Saving'
            coo_utils.SaveCooHDToRCDFile(self.waterLilDiff,self.shape,filename+'_waterDiff',fromlil=True)
            coo_utils.SaveCooHDToRCDFile(self.seedLil,self.shape,filename+'_seeds',fromlil=True)
            coo_utils.SaveCooHDToRCDFile(self.maskLilDiff,self.shape,filename+'_maskDiff',fromlil=True)
            coo_utils.SaveCooHDToRCDFile(self.maskSeedLil,self.shape,filename+'_maskSeeds',fromlil=True)
    def Load(self,filename=None,sLwLD=None,sLwLD_mask=None):
        print 'Load'
        sh = self.shape
        shapeMatch=False
        if sLwLD!=None: # If pre-loaded arrays are passed, they take precedence
            seedLil,waterLilDiff = sLwLD  # unpack the list
            if coo_utils.VerifyCooHDShape(seedLil,sh) and coo_utils.VerifyCooHDShape(waterLilDiff,sh):
                self.seedLil[:] = seedLil
                self.waterLilDiff[:] = waterLilDiff
                shapeMatch=True
        else:          # othersize, try to find a filename
            filename = GetFileBasenameForSaveLoad(filename)
            if filename==None: # In case you didn't mean to do a Load
                print 'No files selected!'
                return
            
            print 'Loading',filename
            shapeWD = coo_utils.GetShapeFromFile( filename+'_waterDiff' )
            shapeS = coo_utils.GetShapeFromFile( filename+'_seeds' )
            if sh == shapeWD == shapeS:
                _, self.waterLilDiff[:] = coo_utils.LoadRCDFileToCooHD(filename+'_waterDiff',tolil=True)
                _, self.seedLil[:] = coo_utils.LoadRCDFileToCooHD(filename+'_seeds',tolil=True)
                shapeMatch=True
        
        if sLwLD_mask!=None:
            maskSeedLil,maskLilDiff = sLwLD_mask  # unpack the list
            if coo_utils.VerifyCooHDShape(maskSeedLil,sh) and coo_utils.VerifyCooHDShape(maskLilDiff,sh):
                self.maskSeedLil[:] = maskSeedLil
                self.maskLilDiff[:] = maskLilDiff
            else:
                print 'Mask passed as argument is not the right shape!'
        elif filename!=None:
            # This should already be done above...
            #filename = GetFileBasenameForSaveLoad(filename)
            
            if sum( [ os.path.exists(filename+i+j)
                     for i in ('_maskSeeds','_maskDiff')
                     for j in ('_rcd.npy','_nnzs.npy','_shape.txt') ] )==6:
                shapeMD = coo_utils.GetShapeFromFile( filename+'_maskDiff' )
                shapeMS = coo_utils.GetShapeFromFile( filename+'_maskSeeds' )
                if sh == shapeMD == shapeMS:
                    _, self.maskLilDiff[:] = coo_utils.LoadRCDFileToCooHD(filename+'_maskDiff',tolil=True)
                    _, self.maskSeedLil[:] = coo_utils.LoadRCDFileToCooHD(filename+'_maskSeeds',tolil=True)
                else:
                    print 'Mask file(s) are the wrong shape! Ignoring!'
            else:
                print 'Cannot find mask, clear the mask instead'
                self.ClearMask()
        
        if not shapeMatch:
            wx.MessageBox('Shapes do not match!!!!!\n'+repr([self.shape,shapeWD,shapeS]))
            return
            
        self.updateWaterArr_t()
    @on_trait_change('saveButton')
    def OnSave(self):
        self.Save()
    @on_trait_change('loadButton')
    def OnLoad(self):
        self.Load()
        self.update_all_plots_cb()
# Not really sure how to make this work right
#    def GetSubArray(self,val):
#        wh = np.where(self.waterArr_t==val)
#        zmin,zmax = min(wh[1]),max(wh[1])
#        ymin,ymax = min(wh[2]),max(wh[2])
#        xmin,xmax = min(wh[3]),max(wh[3])
#        return [ (self.waterArr_t[zmin:zmax+1,ymin:ymax+1,xmin:xmax+1]==val).astype(np.int32)
#                 for i in range(self.shape[0])]
    
    @on_trait_change('volumeRenderButton')
    def OnVolumeRender(self):
        if self.nextSeedValue<2:
            wx.MessageBox('Set "Next seed value" to 2 or higher to render the volume for that region.')
            return
        subArr = self.GetSubArray(self.nextSeedValue)
        vol = ArrayViewVolume(arr=subArr,zscale=self.zscale)
        vol.configure_traits()
        
    @on_trait_change('tempButton')
    def OnTemp(self):
        print 'For testing stuff...'
        print self.waterLilDiff[0][0].dtype
        
        

if __name__=='__main__':
    arr = np.array([ [[[1,2,3,4],[5,6,7,8],[9,10,11,12]],[[1,2,3,4],[5,6,7,8],[9,10,11,12]]], [[[1,2,3,4],[5,6,7,8],[9,10,11,12]],[[1,2,3,4],[5,6,7,8],[9,10,11,12]]] ])
    arr[1] = np.sqrt(arr[1])
    arr[:,1] = arr[:,1]+10
    
    import testArrays
    arr = testArrays.abb3D
    import GifTiffLoader as GTL
    #numLoad=1
    #name = '/media/home/ViibreData/ActiveData/NewSegmentation/AS Edge Wound Healing/2009SEPT24CellCycle05_W2X/','','2009SEPT24Cell_Cycle05_2X20s.tif'
    numLoad=2
    name = '/home/mashbudn/Documents/Drosophila/ActiveData/Resille/Aroshan/2012-04-11/1/Riselle_t','1','.TIF'
    arr0 = GTL.LoadMonolithic(''.join(name))
    arr = np.zeros([numLoad]+list(arr0.shape),dtype=arr0.dtype)
    arr[0] = arr0
    for i in range(1,numLoad):
        arr[i]= GTL.LoadMonolithic(name[0]+str(i+1)+name[2])
    
    a = SeedWaterSegmenter4D(arr=arr)
    a.configure_traits()
