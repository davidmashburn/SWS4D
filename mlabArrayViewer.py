#!/usr/bin/env python
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


# Using the ipw widget interactions instead, remove this later?
#def picker_callback(picker_obj):
#    print picker_obj
#    picked = picker_obj.actors
#    if mesh.actor.actor._vtk_obj in [o._vtk_obj for o in picked]:
#        # m.mlab_source.points is the points array underlying the vtk
#        # dataset. GetPointId return the index in this array.
#        x_, y_ = np.lib.index_tricks.unravel_index(picker_obj.point_id,
#                                                                s.shape)
#        print "Data indices: %i, %i" % (x_, y_)
#        n_x, n_y = s.shape
#        cursor.mlab_source.set(x=x_ - n_x/2.,
#                               y=y_ - n_y/2.)
#        cursor3d.mlab_source.set(x=x[x_, y_],
#                                 y=y[x_, y_],
#                                 z=z[x_, y_])

# This class is the heart of the code; in fact, it contains 90% of what
# is needed for ArrayView4DDual as well.

class ArrayView4D(HasTraits):
    low = Int(0)
    tlength = Property(depends_on=['arr'])
    zlength = Property(depends_on=['arr'])
    ylength = Property(depends_on=['arr'])
    xlength = Property(depends_on=['arr'])
    
    def _get_tlength(self):
        return self.arr.shape[0]-1
    def _get_zlength(self):
        return self.arr.shape[1]-1
    def _get_ylength(self):
        return self.arr.shape[2]-1
    def _get_xlength(self):
        return self.arr.shape[3]-1

    tindex = Range(low='low', high='tlength', value=0, exclude_high=False, mode='slider') # or spinner
    zindex = Range(low='low', high='zlength', value=0, exclude_high=False, mode='slider')
    yindex = Range(low='low', high='ylength', value=0, exclude_high=False, mode='slider')
    xindex = Range(low='low', high='xlength', value=0, exclude_high=False, mode='slider')
    flip = Bool(False)
    
    arr = Array(shape=[None]*4)
    scene = Instance(MlabSceneModel, ())
    plots = List()
    cursors = List()
    numPlots=Int(1)
    numCursors=Int(1)
    
    cursorSize=Int(2)
    plotBuffer=Int(10)
    zscale=Float(2.6)
    
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex'), resizable=True)
    
    def __init__(self,arr,**traits):
        HasTraits.__init__(self,arr=arr,**traits)
        self.initPlotsAndCursors()
    def initPlotsAndCursors(self):
        for i in range(self.numPlots):
            self.plots.append( {'XY':None, 'XZ':None, 'YZ':None} )
        for i in range(self.numCursors):
            self.cursors.append( {'x':None, 'y':None, 'zx':None, 'zy':None} )
    
    def make_plots(self,arr,scene,plots,zeroFill=False):
        # Grab some variables
        xs,ys,zs = arr.shape[3], arr.shape[2], arr.shape[1]        
        plotbuf,zsc = self.plotBuffer,self.zscale
        arrMin,arrMax = arr.min(),arr.max()
        
        # Get the clipped arrays
        xt = arr[self.tindex,:,:,self.xindex].T * (0 if zeroFill else 1)
        yt = arr[self.tindex,:,self.yindex]     * (0 if zeroFill else 1)
        zt = arr[self.tindex,self.zindex]       * (0 if zeroFill else 1)
        
        # Make the 3 array_2d_scources in the pipeline; tell it not to compare
        # so array self-copy will notify traits (see AddMouseInteraction)
        x,y = np.ogrid[:ys,:xs]
        sXY = scene.mlab.pipeline.array2d_source(x,y,zt,comparison_mode=NO_COMPARE)
        #x,y = np.ogrid[ ys+plotbuf : ys+plotbuf+zsc*zs : zsc  ,  :xs ] # right
        x,y = np.ogrid[ 1-zsc*zs-plotbuf:1-plotbuf:zsc  ,  :xs ] # left
        sXZ = scene.mlab.pipeline.array2d_source(x,y,yt,comparison_mode=NO_COMPARE)
        x,y = np.ogrid[ :ys  ,  xs+plotbuf : xs+plotbuf+zsc*zs : zsc ] # top
        #x,y = np.ogrid[ :ys  ,  -zsc*zs-plotbuf : 1-plotbuf : zsc ] # bottom
        sYZ = scene.mlab.pipeline.array2d_source(x,y,xt,comparison_mode=NO_COMPARE)
        
        # Generate the 3 Image Plane Widgets (or Image Actors)
        sList = [sXY,sXZ,sYZ]
        pList = ['XY','XZ','YZ']
        pFunc = scene.mlab.pipeline.image_plane_widget
        # legacy code in case of switch to image_actor instead of ipw
        #pFunc = scene.mlab.pipeline.image_actor
        print plots['XY']
        plots['XY']=1 # Hmph... this list is quite weird...
        print plots['XY']
        for i in range(3):
            # legacy code in case of switch to image_actor instead of ipw
            #plots(pList[i]) = pFunc(sList[i],interpolate=False,
            #                        colormap='gray',vmin=arrMin,vmax=arrMax) )
            plots[pList[i]] = pFunc(sList[i],plane_orientation='z_axes',
                                    colormap='gray',vmin=arrMin,vmax=arrMax)
            plots[pList[i]].ipw.left_button_action = 0
        #plots['XY'].ipw.origin=1
        #plots['XY'].ipw.point1=1
        #plots['XY'].ipw.point2=1
    def quickLine(self,scene,x,y): # pass one list and one value
            xl,yl = hasattr(x,'__len__') , hasattr(y,'__len__')
            if (xl and yl) or ((not xl) and (not yl)):
                print 'Must pass one list and one value!!!'
                return
            elif not xl:
                x = [x,x]
            elif not yl:
                y = [y,y]
            print x,y
            return scene.mlab.plot3d( x, y, [0.1,0.1], [0.1,0.1], color=(1, 0, 0),
                                       tube_radius=self.cursorSize )
    def make_cursors(self,arr,scene,cursors):
        xs,ys,zs = arr.shape[3], arr.shape[2], arr.shape[1]
        plotbuf,zsc = self.plotBuffer,self.zscale
        
        cursors['x']  = self.quickLine( scene, [-plotbuf-zs*zsc,ys], self.xindex )
        cursors['y']  = self.quickLine( scene, self.yindex, [0,plotbuf+xs+zs*zsc] )
        cursors['zx'] = self.quickLine( scene, (self.zindex-zs)*zsc - plotbuf, [0,xs] )
        cursors['zy'] = self.quickLine( scene, [0,ys], plotbuf+xs+self.zindex*zsc )
    def display_scene_helper(self,arr,scene,plots,cursors,zeroFill=False):
        # Interaction properties can only be changed after the scene
        # has been created, and thus the interactor exists
        #self.scene.scene.background = (0, 0, 0)
        
        # Dumped in favor of ipw mouse stuff
        #print 'On Mouse Pick'
        #print self.scene.mayavi_scene._mouse_pick_dispatcher._active_pickers
        #print self.scene.mayavi_scene.on_mouse_pick(picker_callback)
        
        # Set some scene properties
        scene.scene.interactor.interactor_style = tvtk.InteractorStyleImage()
        scene.scene.parallel_projection = True
        scene.scene.anti_aliasing_frames = 0
        scene.mlab.view(-90, 180)  # Secret sauce to make it line up with the standard imagej orientation
        
        # Make the actual plots
        self.make_plots(arr,scene,plots,zeroFill=zeroFill)
        # Make the red lines that display the positions of the other 2 views
        self.make_cursors(arr,scene,cursors)
    
    def update_x_plots(self,arr,plots):
        if plots is not {}:
            plots['YZ'].mlab_source.scalars = arr[self.tindex,:,:,self.xindex].T
    def update_y_plots(self,arr,plots):
        if plots is not {}:
            plots['XZ'].mlab_source.scalars = arr[self.tindex,:,self.yindex,:]
    def update_z_plots(self,arr,plots):
        if plots is not {}:
            plots['XY'].mlab_source.scalars = arr[self.tindex,self.zindex]
    def update_all_plots(self,arr,plots):
        self.update_x_plots(arr,plots)
        self.update_y_plots(arr,plots)
        self.update_z_plots(arr,plots)
    def update_x_cursors(self):
        for cursors in self.cursors:
            cursors['x'].mlab_source.set( y=[self.xindex]*2 )
    def update_y_cursors(self):
        for cursors in self.cursors:
            cursors['y'].mlab_source.set( x=[self.yindex]*2 )
    def update_z_cursors(self):
        xs,ys,zs = self.arr.shape[3], self.arr.shape[2], self.arr.shape[1]
        for cursors in self.cursors:
            cursors['zx'].mlab_source.set( x=[(self.zindex-zs)*self.zscale - self.plotBuffer]*2 )
            cursors['zy'].mlab_source.set( y=[self.plotBuffer+xs+self.zindex*self.zscale]*2 )
    @on_trait_change('scene.activated')
    def display_scene(self):
        print 'Scene activated!'
        self.display_scene_helper(self.arr,self.scene,self.plots[0],self.cursors[0])
    @on_trait_change('xindex')
    def update_x_plots_cb(self):
        self.update_x_plots(self.arr,self.plots[0])
        self.update_x_cursors()
    @on_trait_change('yindex')
    def update_y_plots_cb(self):
        self.update_y_plots(self.arr,self.plots[0])
        self.update_y_cursors()
    @on_trait_change('zindex')
    def update_z_plots_cb(self):
        self.update_z_plots(self.arr,self.plots[0])
        self.update_z_cursors()
    @on_trait_change('tindex')
    def update_all_plots_cb(self):
        self.update_all_plots(self.arr,self.plots[0])

# Same as ArrayView4D but adding vmin and vmax sliders
class ArrayView4DVminVmax(ArrayView4D):
    minI16 = Int(0)
    maxI16 = Int(2**16-1)
    vmin = Range(low='minI16', high='maxI16', value=0, exclude_high=False, mode='slider')
    vmax = Range(low='minI16', high='maxI16', value=0, exclude_high=False, mode='slider')
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex', 'vmin', 'vmax'), resizable=True)
    def display_scene_helper(self,arr,scene,plots,cursors,zeroFill=False,updateVminVmax=False):
        ArrayView4D.display_scene_helper(self,arr,scene,plots,cursors,zeroFill=zeroFill)
        if updateVminVmax:
            self.vmin,self.vmax = arr.min(),arr.max()
    
    @on_trait_change('scene.activated')
    def display_scene(self):
        print 'Scene activated!'
        self.display_scene_helper(self.arr,self.scene,self.plots[0],self.cursors[0],updateVminVmax=True)
    @on_trait_change('vmin,vmax')
    def UpdateVminVmax(self):
        '''Update the 1st set of plots using the sliders'''
        if len(self.plots)>0:
            if 'XY' in self.plots[0]:
                self.plots[0]['XY'].parent.scalar_lut_manager.data_range = self.vmin,self.vmax
                self.plots[0]['XZ'].parent.scalar_lut_manager.data_range = self.vmin,self.vmax
                self.plots[0]['YZ'].parent.scalar_lut_manager.data_range = self.vmin,self.vmax

class ArrayView4DDual(ArrayView4DVminVmax):
    arr2 = Array(shape=[None]*4)
    scene2 = Instance(MlabSceneModel, ())
    numPlots=Int(2)
    numCursors=Int(2)
    
    view = View(VGroup(HGroup(
                    Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                    Item('scene2', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                ),
                Group('xindex','yindex','zindex','tindex','vmin','vmax')), resizable=True)
    def __init__(self,arr,arr2,**traits):
        HasTraits.__init__(self,arr=arr,arr2=arr2,**traits)
        self.initPlotsAndCursors()
    @on_trait_change('scene2.activated')
    def display_scene2(self):
        self.display_scene_helper(self.arr2,self.scene2,self.plots[1],self.cursors[1])
    @on_trait_change('xindex')
    def update_x_plots_cb(self):
        self.update_x_plots(self.arr,self.plots[0])
        self.update_x_plots(self.arr2,self.plots[1])
        self.update_x_cursors()
    @on_trait_change('yindex')
    def update_y_plots_cb(self):
        self.update_y_plots(self.arr,self.plots[0])
        self.update_y_plots(self.arr2,self.plots[1])
        self.update_y_cursors()
    @on_trait_change('zindex')
    def update_z_plots_cb(self):
        self.update_z_plots(self.arr,self.plots[0])
        self.update_z_plots(self.arr2,self.plots[1])
        self.update_z_cursors()
    @on_trait_change('tindex')
    def update_all_plots_cb(self):
        self.update_all_plots(self.arr,self.plots[0])
        self.update_all_plots(self.arr2,self.plots[1])

mouseInteractionModes = ['print','doodle','erase','line','plane','move']

class SeedWaterSegmenter4D(ArrayView4DVminVmax):
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
                                    #if 0<=p[2]<self.arr.shape[1]-1 and 0<=p[0]<self.arr.shape[2]-1 and 0<=p[1]<self.arr.shape[3]-1:
                                    if 0<=p[0]<self.arr.shape[0]-1 and 0<=p[1]<self.arr.shape[1]-1 and 0<=p[2]<self.arr.shape[2]-1 and 0<=p[2]<self.arr.shape[2]-1:
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
                    
                    elif self.mouseInteraction=='erase': # erase mode
                        print 'Erase',position
                    self.update_all_plots_cb()
                    
                    if self.mouseInteraction!='print':
                        plots[view].mlab_source.scalars = plots[view].mlab_source.scalars
                return mouseClick
            
            plots[view].ipw.add_observer('InteractionEvent', genMC(view))
            plots[view].ipw.add_observer('StartInteractionEvent', genMC(view))
    def RunWatershed(self,index='all'):
        tList = ( range(self.arr.shape[0]) if index=='all' else [index] )
        for t in tList:
            self.waterArr[t] = mahotas.cwatershed(self.arr[t],self.seedArr[t])
        
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

class SeedWaterSegmenter4DCompressed(ArrayView4DVminVmax):
    # store the full waterArr and seedArr as cooHD's (actually lil_matrix format) instead
    seedArr_t = Array(shape=[None]*3)
    waterArr_t = Array(shape=[None]*3)
    
    sceneWater = Instance(MlabSceneModel, ())
    
    numPlots=Int(3)
    numCursors=Int(2)
    
    nextSeedValue = Range(low=0, high=10000, value=2, exclude_high=False, mode='spinner')
    #mouseInteraction = String('move')
    mouseInteraction=Enum(mouseInteractionModes)
    watershedButton = Button('Run Watershed')
    updateSeedArr_tButton = Button('UpdateSeedArr_t')
    saveButton = Button('Save')
    loadButton = Button('Load')
    
    tempButton = Button('Temp')
    
    view = View(VGroup(HGroup(
                    Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=600, width=600, show_label=False),
                    Item('sceneWater', editor=SceneEditor(scene_class=MayaviScene), height=600, width=600, show_label=False),
                ),
                Group('xindex','yindex','zindex','tindex','vmin','vmax','mouseInteraction',
                      HGroup('watershedButton','nextSeedValue','updateSeedArr_tButton'),
                      HGroup('saveButton','loadButton','tempButton')
                     )), resizable=True)
    
    def __init__(self,arr,cursorSize=2,**traits):
        HasTraits.__init__(self,arr=arr,**traits)
        self.initPlotsAndCursors()
        # Only really store the waterLilDiffs (see coo_utils for conversions to array)
        # This is NOT the same thing as the SWS3D woutline...
        
        self.waterLilDiff = [ [ scipy.sparse.lil_matrix(arr.shape[2:],dtype=np.int32) # This needs to be able to go negative...
                               for j in range(arr.shape[1]) ]
                             for i in range(arr.shape[0]) ]
        self.seedLil = [ [ scipy.sparse.lil_matrix(arr.shape[2:],dtype=np.uint16)
                            for j in range(arr.shape[1]) ]
                          for i in range(arr.shape[0]) ]
        self.waterArr_t = np.zeros(arr.shape[1:],dtype=np.int32)
        self.seedArr_t = np.zeros(arr.shape[1:],dtype=np.int32)
        
        self.useSeedArr_t=False
        
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
                        self.seedLil[pos[0]][pos[1]][pos[2],pos[3]] = self.nextSeedValue
                        self.seedArr_t[pos[1],pos[2],pos[3]] = self.nextSeedValue
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
                                #if 0<=p[2]<self.arr.shape[1]-1 and 0<=p[0]<self.arr.shape[2]-1 and 0<=p[1]<self.arr.shape[3]-1:
                                if 0<=p[0]<self.arr.shape[0] and 0<=p[1]<self.arr.shape[1] and 0<=p[2]<self.arr.shape[2]-1 and 0<=p[2]<self.arr.shape[2]-1:
                                    for i in range(2):
                                        for j in range(2):
                                            #for k in range(2): # Lose the z fiddle... too confusing
                                                #points.append((p[0]+i,p[1]+j,p[2]+k))
                                                pointsExp.append((p[0],p[1],p[2]+i,p[3]+j))
                            points = np.array(list(set(pointsExp)))
                            
                            #self.seedArr[self.tindex,points[:,2],points[:,0],points[:,1]] = self.nextSeedValue
                            for p in points:
                                self.seedLil[p[0]][p[1]][p[2],p[3]] = self.nextSeedValue
                                if p[0]==self.tindex:
                                    self.seedArr_t[p[1],p[2],p[3]]=self.nextSeedValue
                        
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
                        if self.useSeedArr_t:#hasattr(self,'switch'):
                            print 'arr'
                            self.update_all_plots(self.seedArr_t,self.plots[1]) 
                            #del(self.switch)
                        else:
                            print 'lil'
                            self.update_all_plots(self.seedLil[self.tindex],self.plots[1])
                            #self.switch=None
                        print time.time()-ti
                return mouseClick
            
            plots[view].ipw.add_observer('InteractionEvent', genMC(view))
            plots[view].ipw.add_observer('StartInteractionEvent', genMC(view))
    
    def RunWatershed(self,index='all'):
        tList = ( range(self.arr.shape[0]) if index=='all' else [index] )
        for t in tList:
            self.updateSeedArr_t(t)
            self.waterArr_t = mahotas.cwatershed(self.arr[t],self.seedArr_t)
            self.updateWaterLilDiff(t)
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
    def getWaterArr_t_z(self):
        # This should be the inner function in updateWaterArr_t
        return coo_utils.CooDiffToArray( self.waterLilDiff[self.tindex][self.zindex].toarray() ).astype(np.uint16)
    def updateWaterArr_t(self,tindex=None):
        if tindex==None:
            tindex=self.tindex
        self.waterArr_t[:] = [ coo_utils.CooDiffToArray( self.waterLilDiff[tindex][z].toarray() ).astype(np.uint16)
                              for z in range(self.arr.shape[1]) ]
    def updateSeedArr_t(self,tindex=None):
        if tindex==None:
            tindex=self.tindex
        self.seedArr_t[:] = [ self.seedLil[tindex][z].toarray()
                             for z in range(self.arr.shape[1]) ]
        self.useSeedArr_t = True
    def updateWaterLilDiff(self,tindex=None):
        if tindex==None:
            tindex=self.tindex
        self.waterLilDiff[tindex] = [ scipy.sparse.lil_matrix(coo_utils.ArrayToCooDiff(self.waterArr_t[z]),dtype=np.int32)
                                     for z in range(self.arr.shape[1]) ]
    def update_seeds_overlay(self):
        import time
        t=time.time()
        self.updateSeedArr_t()
        self.update_all_plots(self.seedArr_t,self.plots[1])
    @on_trait_change('updateSeedArr_tButton')
    def updateSeedArr_tCallback(self,tindex=None):
        self.update_seeds_overlay()
        self.updateWaterArr_t()
        self.update_all_plots(self.waterArr_t,self.plots[2])
    @on_trait_change('watershedButton')
    def watershedButtonCallback(self):
        self.RunWatershed(index = self.tindex)
        # waterArr_t and seedArr_t are updated in RunWatershed
        self.update_all_plots(self.seedArr_t,self.plots[1])
        self.update_all_plots(self.waterArr_t,self.plots[2])
    @on_trait_change('nextSeedValue')
    def resetLine(self):
        self.lastPos = None
    @on_trait_change('mouseInteraction')
    def mouseInteractionChanged(self):
        self.lastPos=None
    @on_trait_change('xindex')
    def update_x_plots_cb(self):
        self.update_x_plots(self.arr[self.tindex],self.plots[0])
        if self.useSeedArr_t:
            self.update_x_plots(self.seedArr_t,self.plots[1])
            self.update_x_plots(self.waterArr_t,self.plots[2])
        else:
            self.update_x_plots(self.seedLil[self.tindex],self.plots[1])
            
        self.update_x_cursors()
    @on_trait_change('yindex')
    def update_y_plots_cb(self):
        self.update_y_plots(self.arr[self.tindex],self.plots[0])
        if self.useSeedArr_t:
            self.update_y_plots(self.seedArr_t,self.plots[1])
            self.update_y_plots(self.waterArr_t,self.plots[2])
        else:
            self.update_y_plots(self.seedLil[self.tindex],self.plots[1])
        self.update_y_cursors()
    @on_trait_change('zindex')
    def update_z_plots_cb(self):
        self.update_z_plots(self.arr[self.tindex],self.plots[0])
        if self.useSeedArr_t:
            self.update_z_plots(self.seedArr_t,self.plots[1])
            self.update_z_plots(self.waterArr_t,self.plots[2])
        else:
            self.update_z_plots(self.seedLil[self.tindex],self.plots[1])
            
            # This is quirky, but it should work ok...
            # good compromise...certainly a lot faster!!!
            self.plots[2]['XY'].mlab_source.scalars = self.getWaterArr_t_z()
            self.plots[2]['XZ'].mlab_source.scalars *= 0
            self.plots[2]['YZ'].mlab_source.scalars *= 0
        self.update_z_cursors()
    @on_trait_change('tindex')
    def update_all_plots_cb(self):
        self.update_all_plots(self.arr[self.tindex],self.plots[0])
        self.useSeedArr_t=False
        self.update_all_plots(self.seedLil[self.tindex],self.plots[1])
        
        # This is quirky, but it should work ok...
        # good compromise...certainly a lot faster!!!
        self.plots[2]['XY'].mlab_source.scalars = self.getWaterArr_t_z()
        self.plots[2]['XZ'].mlab_source.scalars *= 0
        self.plots[2]['YZ'].mlab_source.scalars *= 0
        
        
        # Meh, just skip updating the watershed part for speed in editing the seeds...
        # Seriously, how hard is it to push the button
        
        #self.update_seeds_overlay()
        #self.updateWaterArr_t()
        #self.update_all_plots(self.waterArr_t,self.plots[2])
    
    def GetFileBasenameForSaveLoad(self):
        f = wx.FileSelector()
        # Strip off extensions if present on the file
        for i in ['_nnzs.npy','_rcd.npy','_shape.txt']:
            if f[-len(i):]==i:
                f = f[:-len(i)]
        for i in ['_waterDiff','_seeds']:
            if f[-len(i):]==i:
                f = f[:-len(i)]
        return f
    @on_trait_change('saveButton')
    def OnSave(self):
        f = self.GetFileBasenameForSaveLoad()
        if f!=None:
            coo_utils.SaveCooHDToRCDFile(self.waterLilDiff,self.arr.shape,f+'_waterDiff',fromlil=True)
            coo_utils.SaveCooHDToRCDFile(self.seedLil,self.arr.shape,f+'_seeds',fromlil=True)
    @on_trait_change('loadButton')
    def OnLoad(self):
        f = self.GetFileBasenameForSaveLoad()
        shapeWD = coo_utils.GetShapeFromFile( f+'_waterDiff' )
        shapeS = coo_utils.GetShapeFromFile( f+'_seeds' )
        if self.arr.shape == shapeWD == shapeS:
            shapeWD, self.waterLilDiff[:] = coo_utils.LoadRCDFileToCooHD(f+'_waterDiff',tolil=True)
            shapeS, self.seedLil[:] = coo_utils.LoadRCDFileToCooHD(f+'_seeds',tolil=True)
            self.updateSeedArr_t()
            self.updateWaterArr_t()
            self.update_all_plots_cb()
        else:
            wx.MessageBox('Shapes do not match!!!!!\n'+repr([self.arr.shape,shapeWD,shapeS]))
    @on_trait_change('tempButton')
    def OnTemp(self):
        print 'For testing stuff...'
        print self.waterLilDiff[0][0].dtype
    

class ArrayViewVolume(HasTraits):
    low = Int(0)
    tlength = Property(depends_on=['arr'])
    def _get_tlength(self):
        return self.arr.shape[0]-1
    tindex = Range(low='low', high='tlength', value=0, exclude_high=False, mode='slider') # or spinner
    zscale = Int(2.6)
    
    arr = Array(shape=[None]*4)
    
    scene = Instance(MlabSceneModel, ())
    
    vPlot = Instance(PipelineBase)
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('tindex'), resizable=True)
    
    def __init__(self,arr,vmin=None,vmax=None,**traits):
        HasTraits.__init__(self,arr=arr,**traits) # Call __init__ on the super
        self.vmin = (arr.min() if vmin==None else vmin)
        self.vmax = (arr.max() if vmax==None else vmax)
    
    @on_trait_change('scene.activated')
    def make_plot(self):
        x,y,z = np.mgrid[:self.arr.shape[3],:self.arr.shape[2],:self.arr.shape[1]]
        z*=self.zscale
        self.vPlot = self.scene.mlab.pipeline.volume(mlab.pipeline.scalar_field(x,y,z,self.arr[self.tindex].transpose()), vmin=self.vmin, vmax=self.vmax)
    
    @on_trait_change('tindex')
    def update_plot(self):
        self.vPlot.mlab_source.scalars = self.arr[self.tindex]


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
    name = '/home/mashbudn/Documents/VIIBRE--ScarHealing/ActiveData/Resille/2012-04-11/1/Riselle_t','1','.TIF'
    arr0 = GTL.LoadMonolithic(''.join(name))
    arr = np.zeros([numLoad]+list(arr0.shape),dtype=arr0.dtype)
    arr[0] = arr0
    for i in range(1,numLoad):
        arr[i]= GTL.LoadMonolithic(name[0]+str(i+1)+name[2])
    
    #a = ArrayView4D(arr=arr)
    #a = ArrayView4DVminVmax(arr=arr)
    #arr2 = arr//2;arr2[:,:,:10]=0; a = ArrayView4DDual(arr=arr,arr2=arr2)
    #a = SeedWaterSegmenter4D(arr=arr)
    a = SeedWaterSegmenter4DCompressed(arr=arr)
    #a = ArrayViewVolume(arr=arr)
    a.configure_traits()
