#!/usr/bin/env python
import numpy as np

from traits.api import HasTraits, Int, Range, String, Bool, Instance, Property, Array, List, Dict, Button, on_trait_change, NO_COMPARE
from traitsui.api import View, Item, Group, RangeEditor, VGroup, HGroup, VSplit, HSplit, NullEditor
from mayavi.core.api import PipelineBase
from mayavi.core.ui.api import MayaviScene, SceneEditor, MlabSceneModel

from mayavi import mlab
from tvtk.api import tvtk

from np_utils import BresenhamFunction,circs,shprs

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
    plots = Dict()
    cursors = Dict()
    
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex'), resizable=True)
    
    def __init__(self,arr,cursorSize=2,**traits):
        HasTraits.__init__(self,arr=arr,**traits)
        self.cursors = {'x':None, 'y':None, 'zx':None, 'zy':None}        
        self.cursorSize = cursorSize
    
    def display_scene_helper(self,arr,scene,cursors,plots,plotbuf=10,zsc=2.6):
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
        
        # Grab some variables
        xs,ys,zs = arr.shape[3], arr.shape[2], arr.shape[1]        
        arrMin,arrMax = arr.min(),arr.max()
        self.plotBuffer = plotbuf
        self.zscale = zsc
        
        # Get the clipped arrays
        xt = arr[self.tindex,:,:,self.xindex].T
        yt = arr[self.tindex,:,self.yindex]
        zt = arr[self.tindex,self.zindex]
        
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
        for i in range(3):
            # legacy code in case of switch to image_actor instead of ipw
            #plots(pList[i]) = pFunc(sList[i],interpolate=False,
            #                        colormap='gray',vmin=arrMin,vmax=arrMax) )
            plots[pList[i]] = pFunc(sList[i],plane_orientation='z_axes',
                                    colormap='gray',vmin=arrMin,vmax=arrMax)
            plots[pList[i]].ipw.left_button_action = 0
        
        # Make the red lines that display the positions of the other 2 views
        self.MakeCursors(arr,scene,cursors)
    
    def MakeCursors(self,arr,scene,cursors):
        def quickLine(x,y): # pass one list and one value
            xl,yl = hasattr(x,'__len__') , hasattr(y,'__len__')
            if (xl and yl) or ((not xl) and (not yl)):
                print 'Must pass one list and one value!!!'
                return
            elif not xl:
                x = [x,x]
            elif not yl:
                y = [y,y]
            print x,y
            return scene.mlab.plot3d( x, y, [0,0], [0,0], color=(1, 0, 0),
                                       tube_radius=self.cursorSize )
        
        xs,ys,zs = arr.shape[3], arr.shape[2], arr.shape[1]
        plotbuf,zsc = self.plotBuffer,self.zscale
        
        cursors['x']  = quickLine( [-plotbuf-zs*zsc,ys], self.xindex )
        cursors['y']  = quickLine( self.yindex, [0,plotbuf+xs+zs*zsc] )
        cursors['zx'] = quickLine( (self.zindex-zs)*zsc - plotbuf, [0,xs] )
        cursors['zy'] = quickLine( [0,ys], plotbuf+xs+self.zindex*zsc )
    
    def update_all_plots(self,arr,plots):
        if plots is not {}:
            plots['XY'].mlab_source.scalars = arr[self.tindex,self.zindex]
            plots['XZ'].mlab_source.scalars = arr[self.tindex,:,self.yindex,:]
            plots['YZ'].mlab_source.scalars = arr[self.tindex,:,:,self.xindex].T
    def update_x_plots(self,arr,plots,cursors):
        if plots is not {}:
            plots['YZ'].mlab_source.scalars = arr[self.tindex,:,:,self.xindex].T
            cursors['x'].mlab_source.set( y=[self.xindex]*2 )
    def update_y_plots(self,arr,plots,cursors):
        if plots is not {}:
            plots['XZ'].mlab_source.scalars = arr[self.tindex,:,self.yindex,:]
            cursors['y'].mlab_source.set( x=[self.yindex]*2 )
    def update_z_plots(self,arr,plots,cursors):
        xs,ys,zs = self.arr.shape[3],self.arr.shape[2],self.arr.shape[1]
        if plots is not {}:
            plots['XY'].mlab_source.scalars = arr[self.tindex,self.zindex]
            cursors['zx'].mlab_source.set( x=[(self.zindex-zs)*self.zscale - self.plotBuffer]*2 )
            cursors['zy'].mlab_source.set( y=[self.plotBuffer+xs+self.zindex*self.zscale]*2 )
    
    @on_trait_change('scene.activated')
    def display_scene(self):
        print 'Scene activated!'
        self.display_scene_helper(self.arr,self.scene,self.cursors,self.plots)
    @on_trait_change('tindex')
    def update_all_plots_cb(self):
        self.update_all_plots(self.arr,self.plots)
    @on_trait_change('xindex')
    def update_x_plots_cb(self):
        self.update_x_plots(self.arr,self.plots,self.cursors)
    @on_trait_change('yindex')
    def update_y_plots_cb(self):
        self.update_y_plots(self.arr,self.plots,self.cursors)
    @on_trait_change('zindex')
    def update_z_plots_cb(self):
        self.update_z_plots(self.arr,self.plots,self.cursors)

# Same as ArrayView4D but adding vmin and vmax sliders
class ArrayView4DVminVmax(ArrayView4D):
    minI16 = Int(0)
    maxI16 = Int(2**16)
    vmin = Range(low='minI16', high='maxI16', value=0, exclude_high=False, mode='slider')
    vmax = Range(low='minI16', high='maxI16', value=0, exclude_high=False, mode='slider')
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex', 'vmin', 'vmax'), resizable=True)
    def display_scene_helper(self,arr,scene,cursors,plots,updateVminVmax=False):
        ArrayView4D.display_scene_helper(self,arr,scene,cursors,plots)
        if updateVminVmax:
            self.vmin,self.vmax = arr.min(),arr.max()
    
    @on_trait_change('scene.activated')
    def display_scene(self):
        print 'Scene activated!'
        self.display_scene_helper(self.arr,self.scene,self.cursors,self.plots,updateVminVmax=True)
    @on_trait_change('vmin,vmax')
    def UpdateVminVmax(self):
        '''Update the 1st set of plots using the sliders'''
        if 'XY' in self.plots:
            self.plots['XY'].parent.scalar_lut_manager.data_range = self.vmin,self.vmax
            self.plots['XZ'].parent.scalar_lut_manager.data_range = self.vmin,self.vmax
            self.plots['YZ'].parent.scalar_lut_manager.data_range = self.vmin,self.vmax

class ArrayView4DDual(ArrayView4DVminVmax):
    arr2 = Array(shape=[None]*4)
    scene2 = Instance(MlabSceneModel, ())
    plots2 = Dict()
    cursors2 = Dict()
    
    view = View(VGroup(HGroup(
                    Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                    Item('scene2', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                ),
                Group('xindex','yindex','zindex','tindex','vmin','vmax')), resizable=True)
    def __init__(self,arr,arr2,cursorSize=2,**traits):
        HasTraits.__init__(self,arr=arr,arr2=arr2,**traits)
        self.cursors = {'x':None, 'y':None, 'zx':None, 'zy':None}        
        self.cursors2 = {'x':None, 'y':None, 'zx':None, 'zy':None}
        self.cursorSize = cursorSize
    @on_trait_change('scene2.activated')
    def display_scene2(self):
        self.display_scene_helper(self.arr2,self.scene2,self.cursors2,self.plots2)
    @on_trait_change('tindex')
    def update_all_plots_cb(self):
        self.update_all_plots(self.arr,self.plots)
        self.update_all_plots(self.arr2,self.plots2)
    @on_trait_change('xindex')
    def update_x_plots_cb(self):
        self.update_x_plots(self.arr,self.plots,self.cursors)
        self.update_x_plots(self.arr2,self.plots2,self.cursors2)
    @on_trait_change('yindex')
    def update_y_plots_cb(self):
        self.update_y_plots(self.arr,self.plots,self.cursors)
        self.update_y_plots(self.arr2,self.plots2,self.cursors2)
    @on_trait_change('zindex')
    def update_z_plots_cb(self):
        self.update_z_plots(self.arr,self.plots,self.cursors)
        self.update_z_plots(self.arr2,self.plots2,self.cursors2)

mouseInteractionModes = ['print','doodle','erase','line','plane']

class ArrayViewDoodle(ArrayView4DDual):
    seedArr = Array(shape=[None]*4)
    
    mouseInteraction = String('line')
    
    def __init__(self,arr,arr2,seedArr=None,cursorSize=2,**traits):
        ArrayView4DDual.__init__(self,arr=arr,arr2=arr2,cursorSize=cursorSize,**traits)
        if seedArr==None:
            self.seedArr = arr*0+1
        else:
            self.seedArr = seedArr
        self.lastPos=None
    def display_scene_helper(self,arr,scene,cursors,plots,updateVminVmax=False):
        ArrayView4DDual.display_scene_helper(self,arr,scene,cursors,plots,updateVminVmax=updateVminVmax)
        for s in ('XY','XZ','YZ'):
            plots[s].mlab_source.scalars = np.array(plots[s].mlab_source.scalars)
        self.AddMouseInteraction()
    def AddMouseInteraction(self):
        # the heart of the mouse interactions
        def mouseClick(obj, evt):
            position = obj.GetCurrentCursorPosition()
            if self.mouseInteraction not in mouseInteractionModes:
                print 'ERROR! UNSUPPORTED MODE!'
                return
            elif self.mouseInteraction=='print':
                print position
            elif self.mouseInteraction=='doodle':
                print 'Doodle',position
                self.seedArr[self.tindex,self.zindex,position[0],position[1]] = 0
                self.plots['XY'].mlab_source.scalars[position[0],position[1]] = 0
                #self.plots['XY'].mlab_source.scalars = self.arr[self.tindex,self.zindex,:,:] # complete rebuild
            elif self.mouseInteraction=='erase': # erase mode
                print 'Erase',position
            elif self.mouseInteraction=='line':
                if self.lastPos==None:
                    self.seedArr[self.tindex,self.zindex,position[0],position[1]] = 0
                    self.plots['XY'].mlab_source.scalars[position[0],position[1]] = 0
                else:
                    points = BresenhamFunction(map(int,position[:2]),map(int,self.lastPos[:2]))
                    self.seedArr[self.tindex,self.zindex,[i[0] for i in points],[i[1] for i in points]] = 0
                    self.plots['XY'].mlab_source.scalars[[i[0] for i in points],[i[1] for i in points]] = 0
                
                self.lastPos = position
            
            if self.mouseInteraction!='print':
                self.plots['XY'].mlab_source.scalars = self.plots['XY'].mlab_source.scalars
        
        self.plots['XY'].ipw.add_observer('InteractionEvent', mouseClick)
        self.plots['XY'].ipw.add_observer('StartInteractionEvent', mouseClick)
    def update_all_plots(self,arr,plots):
        if plots is not {}:
            plots['XY'].mlab_source.scalars = arr[self.tindex,self.zindex]*self.seedArr[self.tindex,self.zindex]
            plots['XZ'].mlab_source.scalars = arr[self.tindex,:,self.yindex,:]*self.seedArr[self.tindex,:,self.yindex,:]
            plots['YZ'].mlab_source.scalars = arr[self.tindex,:,:,self.xindex].T*self.seedArr[self.tindex,:,:,self.xindex].T
    def update_x_plots(self,arr,plots,cursors):
        if plots is not {}:
            plots['YZ'].mlab_source.scalars = arr[self.tindex,:,:,self.xindex].T*self.seedArr[self.tindex,:,:,self.xindex].T
            cursors['x'].mlab_source.set( y=[self.xindex]*2 )
    def update_y_plots(self,arr,plots,cursors):
        if plots is not {}:
            plots['XZ'].mlab_source.scalars = arr[self.tindex,:,self.yindex,:]*self.seedArr[self.tindex,:,self.yindex,:]
            cursors['y'].mlab_source.set( x=[self.yindex]*2 )
    def update_z_plots(self,arr,plots,cursors):
        xs,ys,zs = self.arr.shape[3],self.arr.shape[2],self.arr.shape[1]
        if plots is not {}:
            plots['XY'].mlab_source.scalars = arr[self.tindex,self.zindex]*self.seedArr[self.tindex,self.zindex]
            cursors['zx'].mlab_source.set( x=[(self.zindex-zs)*self.zscale - self.plotBuffer]*2 )
            cursors['zy'].mlab_source.set( y=[self.plotBuffer+xs+self.zindex*self.zscale]*2 )
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
        # This really doesn't gain me anything...
        x,y,z = np.mgrid[:arr.shape[3],:arr.shape[2],:arr.shape[1]]
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
    numLoad=1
    name = '/media/home/ViibreData/ActiveData/NewSegmentation/AS Edge Wound Healing/2009SEPT24CellCycle05_W2X/','','2009SEPT24Cell_Cycle05_2X20s.tif'
    #name = '/home/mashbudn/Documents/VIIBRE--ScarHealing/ActiveData/Resille/2012-04-11/1/Riselle_t','1','.TIF'
    arr0 = GTL.LoadMonolithic(''.join(name))
    arr = np.zeros([numLoad]+list(arr0.shape),dtype=arr0.dtype)
    arr[0] = arr0
    for i in range(1,numLoad):
        arr[i]= GTL.LoadMonolithic(name[0]+str(i+1)+name[2])
    
    #a = ArrayViewDoodle(arr=arr,arr2=np.array(arr)*-1)
    a = ArrayViewVolume(arr=arr)
    a.configure_traits()
