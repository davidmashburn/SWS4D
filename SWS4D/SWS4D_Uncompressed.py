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

from mlabArrayViewer import ArrayViewVolume,ArrayView4D,ArrayView4DVminVmax,ArrayView4DDual
from SWS4D_utils import GetFileBasenameForSaveLoad,LoadMostRecentSegmentation

mouseInteractionModes = ['print','doodle','line','plane','move']

class SeedWaterSegmenter4D(ArrayView4DVminVmax):
    '''This is the original version of SWS4D ... it does not support save or load because they would be far too disk-intensive!!!'''
    seedArr = Array(shape=[None]*4)
    waterArr = Array(shape=[None]*4)
    
    sceneWater = Instance(MlabSceneModel, ())
    
    numPlots=Int(3)
    numCursors=Int(2)
    
    nextSeedValue = Range(low=0, high=10000, value=2, exclude_high=False, mode='spinner')
    mouseInteraction = String('line')
    watershedButton = Button('Run Watershed')
    
    view = View(VGroup(HGroup(
                    Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=600, width=600, show_label=False),
                    Item('sceneWater', editor=SceneEditor(scene_class=MayaviScene), height=600, width=600, show_label=False),
                ),
                Group('xindex','yindex','zindex','tindex','vmin','vmax','watershedButton','nextSeedValue')), resizable=True)
    
    def __init__(self,arr,waterArr=None,seedArr=None,cursorSize=2,**traits):
        HasTraits.__init__(self,arr=arr,**traits)
        self.shape = arr.shape
        self.initPlotsAndCursors()
        
        self.waterArr = ( arr*0 if waterArr==None else waterArr )
        self.seedArr = ( arr*0 if seedArr==None else seedArr )
        
        self.lastPos=None
        self.lastPos2=None
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
                        self.seedArr[pos[0],pos[1],pos[2],pos[3]] = self.nextSeedValue
                        #self.plots['XY'].mlab_source.scalars[pos[0],pos[1]] = self.nextSeedValue
                        
                        if self.lastPos!=None:
                            if self.mouseInteraction == 'line':
                                points = np.array(BresenhamFunction(pos,self.lastPos))
                            elif self.mouseInteraction == 'plane':
                                planepoints = BresenhamTriangle(pos,self.lastPos,self.lastPos2)
                                points = []
                                for p in planepoints:
                                    #if 0<=p[2]<self.shape[1]-1 and 0<=p[0]<self.shape[2]-1 and 0<=p[1]<self.shape[3]-1:
                                    if 0<=p[0]<self.shape[0]-1 and 0<=p[1]<self.shape[1]-1 and 0<=p[2]<self.shape[2]-1 and 0<=p[2]<self.shape[2]-1:
                                        for i in range(2):
                                            for j in range(2):
                                                #for k in range(2): # Lose the z fiddle... too confusing
                                                    #points.append((p[0]+i,p[1]+j,p[2]+k))
                                                    points.append((p[0]+i,p[1]+j,p[2],p[3]))
                                points = np.array(list(set(points)))
                            else:
                                points=[]
                            
                            if points!=[]:
                                #self.seedArr[self.tindex,points[:,2],points[:,0],points[:,1]] = self.nextSeedValue
                                self.seedArr[points[:,0],points[:,1],points[:,2],points[:,3]] = self.nextSeedValue
                        
                        if self.mouseInteraction == 'line' and not np.sum(self.lastPos!=pos)==0:
                            self.lastPos = pos
                        elif self.mouseInteraction == 'plane' and not np.sum(self.lastPos!=pos)==0:
                            self.lastPos, self.lastPos2 = pos, self.lastPos
                    
                    self.update_all_plots_cb()
                    
                    if self.mouseInteraction!='print':
                        plots[view].mlab_source.scalars = plots[view].mlab_source.scalars
                return mouseClick
            
            plots[view].ipw.add_observer('InteractionEvent', genMC(view))
            plots[view].ipw.add_observer('StartInteractionEvent', genMC(view))
    def RunWatershed(self,index='all'):
        tList = ( range(self.shape[0]) if index=='all' else [index] )
        for t in tList:
            self.waterArr[t] = mahotas.cwatershed(self.arr[t],self.seedArr[t])
            print 'Watershed on frame',t
        
        self.lastPos=None
    @on_trait_change('scene.activated')
    def display_scene(self):
        self.display_scene_helper(self.arr,self.scene,self.plots[0],self.cursors[0])
        self.make_plots(self.seedArr,self.scene,self.plots[1])
        for plots in self.plots[:2]:
            for s in ('XY','XZ','YZ'):
                plots[s].mlab_source.scalars = np.array(plots[s].mlab_source.scalars)
        self.AddMouseInteraction(self.plots[0])
        self.SetMapPlotColormap(self.plots[1],clearBG=True)
    @on_trait_change('sceneWater.activated')
    def display_sceneWater(self):
        self.display_scene_helper(self.waterArr,self.sceneWater,self.plots[2],self.cursors[1])
        for plots in self.plots[2:]:
            for s in ('XY','XZ','YZ'):
                plots[s].mlab_source.scalars = np.array(plots[s].mlab_source.scalars)
        self.SetMapPlotColormap(self.plots[2])
        self.AddMouseInteraction(self.plots[2])
    @on_trait_change('watershedButton')
    def watershedButtonCallback(self):
        self.RunWatershed(index = self.tindex)
        self.update_all_plots(self.seedArr,self.plots[1])
        self.update_all_plots(self.waterArr,self.plots[2])
    @on_trait_change('nextSeedValue')
    def resetLine(self):
        self.lastPos = None
    @on_trait_change('xindex')
    def update_x_plots_cb(self):
        self.update_x_plots(self.arr,self.plots[0])
        self.update_x_plots(self.seedArr,self.plots[1])
        self.update_x_plots(self.waterArr,self.plots[2])
        self.update_x_cursors()
    @on_trait_change('yindex')
    def update_y_plots_cb(self):
        self.update_y_plots(self.arr,self.plots[0])
        self.update_y_plots(self.seedArr,self.plots[1])
        self.update_y_plots(self.waterArr,self.plots[2])
        self.update_y_cursors()
    @on_trait_change('zindex')
    def update_z_plots_cb(self):
        self.update_z_plots(self.arr,self.plots[0])
        self.update_z_plots(self.seedArr,self.plots[1])
        self.update_z_plots(self.waterArr,self.plots[2])
        self.update_z_cursors()
    @on_trait_change('tindex')
    def update_all_plots_cb(self):
        self.update_all_plots(self.arr,self.plots[0])
        self.update_all_plots(self.seedArr,self.plots[1])
        self.update_all_plots(self.waterArr,self.plots[2])

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
