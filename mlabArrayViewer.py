#!/usr/bin/env python
import numpy as np

from traits.api import HasTraits, Int, Range, Bool, Instance, Property, Array, List, Button, on_trait_change
from traitsui.api import View, Item, Group, RangeEditor, VGroup, HGroup, VSplit, HSplit, NullEditor
from mayavi.core.api import PipelineBase
from mayavi.core.ui.api import MayaviScene, SceneEditor, MlabSceneModel

from mayavi import mlab
from tvtk.api import tvtk

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
    arr2 = Array(shape=[None]*4)
    
    scene = Instance(MlabSceneModel, ())
    scene2 = Instance(MlabSceneModel, ())
    
    plotXY = Instance(PipelineBase)
    plotXZ = Instance(PipelineBase)
    plotYZ = Instance(PipelineBase)
    
    plotXY2 = Instance(PipelineBase)
    plotXZ2 = Instance(PipelineBase)
    plotYZ2 = Instance(PipelineBase)
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex'), resizable=True)
    
    def __init__(self,arr,arr2=None,cursorSize=2,**traits):
        if arr2==None:
            HasTraits.__init__(self,arr=arr,**traits) # Call __init__ on the super
        else:
            HasTraits.__init__(self,arr=arr,arr2=arr2,**traits) # Call __init__ on the super
            self.cursors2 = {'x':None, 'y':None, 'zx':None, 'zy':None}
        self.cursors = {'x':None, 'y':None, 'zx':None, 'zy':None}        
        self.cursorSize = cursorSize
    
    def display_scene_helper(self,arr,scene,cursors,number=''): # Number is either nothing or '2'
        if number not in ['','2']:
            print "Number must be '' or '2'"
            return
        # Interaction properties can only be changed after the scene
        # has been created, and thus the interactor exists
        #self.scene.scene.background = (0, 0, 0)
        scene.scene.interactor.interactor_style = tvtk.InteractorStyleImage()
        scene.scene.parallel_projection = True
        scene.mlab.view(-90, 180)  # Secret sauce to make it line up with the standard imagej orientation
        
        print self.xindex, self.yindex,self.zindex, self.tindex
        
        xs,ys,zs = arr.shape[3], arr.shape[2], arr.shape[1]
        
        arrMin,arrMax = arr.min(),arr.max()
        
        self.plotBuffer = plotbuf = 10
        self.zscale = zsc = 2.6
        
        xt = arr[self.tindex,:,:,self.xindex].T
        yt = arr[self.tindex,:,self.yindex]
        zt = arr[self.tindex,self.zindex]
        
        x,y = np.ogrid[:ys,:xs]
        sXY = scene.mlab.pipeline.array2d_source(x,y,zt)
        #x,y = np.ogrid[ ys+plotbuf : ys+plotbuf+zsc*zs : zsc  ,  :xs ] # right
        x,y = np.ogrid[ 1-zsc*zs-plotbuf:1-plotbuf:zsc  ,  :xs ] # left
        sXZ = scene.mlab.pipeline.array2d_source(x,y,yt)
        x,y = np.ogrid[ :ys  ,  xs+plotbuf : xs+plotbuf+zsc*zs : zsc ] # top
        #x,y = np.ogrid[ :ys  ,  -zsc*zs-plotbuf : 1-plotbuf : zsc ] # bottom
        sYZ = scene.mlab.pipeline.array2d_source(x,y,xt)
        
        sList = [sXY,sXZ,sYZ]
        pList = [i+number for i in ['plotXY','plotXZ','plotYZ']]
        pFunc = scene.mlab.pipeline.image_plane_widget #scene.mlab.pipeline.image_actor
        for i in range(3):
            #setattr( self, pList[i], pFunc(sList[i],interpolate=False,
            #                               colormap='gray',vmin=arrMin,vmax=arrMax) )
            setattr( self, pList[i], pFunc(sList[i],plane_orientation='z_axes',
                                           colormap='gray',vmin=arrMin,vmax=arrMax) )
            getattr( self, pList[i]).ipw.left_button_action = 0
            
        
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
        
        cursors['x']  = quickLine( [-plotbuf-zs*zsc,ys], self.xindex )
        cursors['y']  = quickLine( self.yindex, [0,plotbuf+xs+zs*zsc] )
        cursors['zx'] = quickLine( (self.zindex-zs)*zsc - plotbuf, [0,xs] )
        cursors['zy'] = quickLine( [0,ys], plotbuf+xs+self.zindex*zsc )
    
    @on_trait_change('scene.activated')
    def display_scene(self):
        print 'Scene activated!'
        self.display_scene_helper(self.arr,self.scene,self.cursors)
    @on_trait_change('scene2.activated')
    def display_scene2(self):
        self.display_scene_helper(self.arr2,self.scene2,self.cursors2,number='2')
    @on_trait_change('tindex')
    def update_all_plots(self):
        if self.plotXY is not None:
            self.plotXY.mlab_source.scalars = self.arr[self.tindex,self.zindex]
            self.plotXZ.mlab_source.scalars = self.arr[self.tindex,:,self.yindex,:]
            self.plotYZ.mlab_source.scalars = self.arr[self.tindex,:,:,self.xindex].T
        if self.plotXY2 is not None:
            self.plotXY2.mlab_source.scalars = self.arr2[self.tindex,self.zindex]
            self.plotXZ2.mlab_source.scalars = self.arr2[self.tindex,:,self.yindex,:]
            self.plotYZ2.mlab_source.scalars = self.arr2[self.tindex,:,:,self.xindex].T
    @on_trait_change('xindex')
    def update_x_plots(self):
        if self.plotXY is not None:
            self.plotYZ.mlab_source.scalars = self.arr[self.tindex,:,:,self.xindex].T
            self.cursors['x'].mlab_source.set( y=[self.xindex]*2 )
        if self.plotXY2 is not None:
            self.plotYZ2.mlab_source.scalars = self.arr2[self.tindex,:,:,self.xindex].T
            self.cursors2['x'].mlab_source.set( y=[self.xindex]*2 )
    @on_trait_change('yindex')
    def update_y_plots(self):
        if self.plotXY is not None:
            self.plotXZ.mlab_source.scalars = self.arr[self.tindex,:,self.yindex,:]
            self.cursors['y'].mlab_source.set( x=[self.yindex]*2 )
        if self.plotXY2 is not None:
            self.plotXZ2.mlab_source.scalars = self.arr2[self.tindex,:,self.yindex,:]
            self.cursors2['y'].mlab_source.set( x=[self.yindex]*2 )
    @on_trait_change('zindex')
    def update_z_plots(self):
        xs,ys,zs = self.arr.shape[3],self.arr.shape[2],self.arr.shape[1]
        
        if self.plotXY is not None:
            self.plotXY.mlab_source.scalars = self.arr[self.tindex,self.zindex]
            self.cursors['zx'].mlab_source.set( x=[(self.zindex-zs)*self.zscale - self.plotBuffer]*2 )
            self.cursors['zy'].mlab_source.set( y=[self.plotBuffer+xs+self.zindex*self.zscale]*2 )
        if self.plotXY2 is not None:
            self.plotXY2.mlab_source.scalars = self.arr2[self.tindex,self.zindex]
            self.cursors2['zx'].mlab_source.set( x=[(self.zindex-zs)*self.zscale - self.plotBuffer]*2 )
            self.cursors2['zy'].mlab_source.set( y=[self.plotBuffer+xs+self.zindex*self.zscale]*2 )

class ArrayView4DDual(ArrayView4D):
    # The layout of the dialog created
    view = View(VGroup(HGroup(
                    Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                    Item('scene2', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                ),
                Group('xindex','yindex','zindex', 'tindex')), resizable=True)
    def __init__(self,arr,arr2,cursorSize=2,**traits):
        ArrayView4D.__init__(self,arr=arr,arr2=arr2,**traits) # Call __init__ on the super

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
    
    a = ArrayView4DDual(arr=arr,arr2=np.array(arr)*-1)
    a.configure_traits()
