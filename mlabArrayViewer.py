#!/usr/bin/env python
import numpy as np

from traits.api import HasTraits, Int, Range, Instance, Property, Array, List, Button, on_trait_change
from traitsui.api import View, Item, Group, RangeEditor, VGroup, HGroup, VSplit, HSplit, NullEditor
from mayavi.core.api import PipelineBase
from mayavi.core.ui.api import MayaviScene, SceneEditor, MlabSceneModel

from mayavi import mlab

class ArrayView4D(HasTraits):
    low = Int(0)
    tlength = Property(depends_on=['arr'])
    zlength = Property(depends_on=['arr'])

    def _get_tlength(self):
        return self.arr.shape[0]-1
    def _get_zlength(self):
        return self.arr.shape[1]-1

    tindex = Range(low='low', high='tlength', value=0, exclude_high=False, mode='spinner')
    zindex = Range(low='low', high='zlength', value=0, exclude_high=False, mode='spinner')
    
    arr = Array(shape=[None]*4)
    
    scene = Instance(MlabSceneModel, ())
    plot = Instance(PipelineBase)
    
    @on_trait_change('zindex,tindex')
    def update_plot(self):
        print self.zindex, self.tindex
        if self.plot is None:
            self.plot = self.scene.mlab.imshow( self.arr[self.tindex,self.zindex], colormap='gray' )
        else:
            self.plot.mlab_source.set(scalars=self.arr[self.tindex,self.zindex])
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('zindex', 'tindex'), resizable=True)

class ArrayView4DTri(HasTraits):
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

    tindex = Range(low='low', high='tlength', value=1, exclude_high=False, mode='slider')
    zindex = Range(low='low', high='zlength', value=1, exclude_high=False, mode='spinner')
    yindex = Range(low='low', high='ylength', value=1, exclude_high=False, mode='spinner')
    xindex = Range(low='low', high='xlength', value=1, exclude_high=False, mode='spinner')
    
    arr = Array(shape=[None]*4)
    
    sceneXY = Instance(MlabSceneModel, ())
    sceneXZ = Instance(MlabSceneModel, ())
    sceneYZ = Instance(MlabSceneModel, ())
    
    plotXY = Instance(PipelineBase)
    plotXZ = Instance(PipelineBase)
    plotYZ = Instance(PipelineBase)
    
    ##@on_trait_change('tindex,zindex,yindex,xindex')
    ##def update_plot(self):
    ##    print self.tindex, self.zindex,self.yindex, self.xindex
    ##    if self.plotXY is None:
    ##        self.plotXY = self.sceneXY.mlab.surf( self.arr[self.tindex,self.zindex,:,:], colormap='gray' )
    ##        self.plotXZ = self.sceneXZ.mlab.surf( self.arr[self.tindex,:,self.yindex,:], colormap='gray' )
    ##        self.plotYZ = self.sceneYZ.mlab.surf( self.arr[self.tindex,:,:,self.xindex], colormap='gray' )
    ##    else:
    ##        self.plotXY.mlab_source.set(scalars=self.arr[self.tindex,self.zindex,:,:])
    ##        self.plotXZ.mlab_source.set(scalars=self.arr[self.tindex,:,self.yindex,:])
    ##        self.plotYZ.mlab_source.set(scalars=self.arr[self.tindex,:,:,self.xindex])
    
    @on_trait_change('tindex,zindex,yindex,xindex')
    def update_plot(self):
        if self.plotXY is None:
            self.plotXY = mlab.imshow(self.arr[self.tindex,self.zindex,:,:], colormap='gray', figure=self.sceneXY.mayavi_scene)  
            self.plotXZ = mlab.imshow(self.arr[self.tindex,:,self.yindex,:], colormap='gray', figure=self.sceneXZ.mayavi_scene)
            self.plotYZ = mlab.imshow(self.arr[self.tindex,:,:,self.xindex].T, colormap='gray', figure=self.sceneYZ.mayavi_scene)
        else:
            self.plotXY.mlab_source.set(scalars=self.arr[self.tindex,self.zindex,:,:])
            self.plotXZ.mlab_source.set(scalars=self.arr[self.tindex,:,self.yindex,:])
            self.plotYZ.mlab_source.set(scalars=self.arr[self.tindex,:,:,self.xindex].T)

    
    # The layout of the dialog created
    view = View(
                VGroup(
                  VSplit(
                    Item('sceneYZ', editor=SceneEditor(scene_class=MayaviScene), height=300, width=300, show_label=False),
                    HSplit(
                        Item('sceneXY', editor=SceneEditor(scene_class=MayaviScene), height=300, width=300, show_label=False),
                        Item('sceneXZ', editor=SceneEditor(scene_class=MayaviScene), height=300, width=300, show_label=False),
                    ),
                  ),
                  Group('xindex','yindex','zindex', 'tindex'),
                ),
                resizable=True)


if __name__=='__main__':
    arr = np.array([ [[[1,2,3,4],[5,6,7,8],[9,10,11,12]],[[1,2,3,4],[5,6,7,8],[9,10,11,12]]], [[[1,2,3,4],[5,6,7,8],[9,10,11,12]],[[1,2,3,4],[5,6,7,8],[9,10,11,12]]] ])
    arr[1] = np.sqrt(arr[1])
    arr[:,1] = arr[:,1]+10
    
    import testArrays
    arr = testArrays.abb3D
    import GifTiffLoader as GTL
    arr = GTL.LoadMonolithic('/home/mashbudn/Documents/VIIBRE--ScarHealing/ActiveData/Resille/2012-04-11/1/Riselle_t1.TIF')
    
    a = ArrayView4DTri(arr=np.array([arr]))
    a.configure_traits()
