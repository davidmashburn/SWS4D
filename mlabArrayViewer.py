#!/usr/bin/env python
import numpy as np

from traits.api import HasTraits, Int, Range, Bool, Instance, Property, Array, List, Button, on_trait_change
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

class ArrayViewTriIPWs(HasTraits):
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

    tindex = Range(low='low', high='tlength', value=1, exclude_high=False, mode='slider') # or spinner
    zindex = Range(low='low', high='zlength', value=1, exclude_high=False, mode='slider')
    yindex = Range(low='low', high='ylength', value=1, exclude_high=False, mode='slider')
    xindex = Range(low='low', high='xlength', value=1, exclude_high=False, mode='slider')
    flip = Bool(False)
    
    arr = Array(shape=[None]*4)
    
    scene = Instance(MlabSceneModel, ())
    
    plotXY = Instance(PipelineBase)
    plotXZ = Instance(PipelineBase)
    plotYZ = Instance(PipelineBase)
    
    
    @on_trait_change('xindex,yindex,zindex,tindex')
    def update_plot(self):
        arr = self.arr
        print self.xindex, self.yindex,self.zindex, self.tindex
        if not hasattr(self,'min'):
            self.min = arr.min()
            self.max = arr.max()
        
        buffer = 10
        
        xt = arr[self.tindex,:,:,self.xindex].T
        yt = arr[self.tindex,:,self.yindex]
        zt = arr[self.tindex,self.zindex]
        
        arr_min = min(xt.min(),yt.min,zt.min())
        arr_max = max(xt.max(),yt.max(),zt.max())

        if self.plotXY is None:
            x,y = np.ogrid[:arr.shape[2],:arr.shape[3]]
            s = self.scene.mlab.pipeline.array2d_source(x,y,zt)
            self.plotXY = self.scene.mlab.pipeline.image_actor(s,interpolate=False, colormap='gray', vmin=arr.min(), vmax=arr.max())
            
            zscale=2.6
            x,y = np.ogrid[ arr.shape[2]+buffer : arr.shape[2]+buffer+zscale*arr.shape[1] : zscale  ,  :arr.shape[3] ] # right
            #x,y = np.ogrid[ -zscale*arr.shape[1]-buffer:1-buffer:zscale  ,  :arr.shape[3] ] # left
            s = self.scene.mlab.pipeline.array2d_source(x,y,yt)
            self.plotXZ = self.scene.mlab.pipeline.image_actor(s,interpolate=False, colormap='gray', vmin=arr.min(), vmax=arr.max())
            
            x,y = np.ogrid[ :arr.shape[2]  ,  arr.shape[3]+buffer : arr.shape[3]+buffer+zscale*arr.shape[1] : zscale ] # top
            #x,y = np.ogrid[ :arr.shape[2]  ,  -zscale*arr.shape[1]-buffer:1-buffer:zscale ] # bottom
            s = self.scene.mlab.pipeline.array2d_source(x,y,xt)
            self.plotYZ = self.scene.mlab.pipeline.image_actor(s,interpolate=False, colormap='gray', vmin=arr.min(), vmax=arr.max())
            
            #x,y,z = np.mgrid[10*i:10+10*i:len()*1j,10*i:10+10*i:0.5,0:0.5:0.5]
            #arr = testArrays.ab2D[:20,:20,None]
            #s = mayavi.tools.pipeline.scalar_field(x,y,z,arr)
            #ia = mayavi.mlab.pipeline.image_plane_widget(s,plane_orientation='z_axes')
            
            #self.plot = self.scene.mlab.imshow( arrExp, colormap='gray', vmin=arr.min(), vmax=arr.max())
        else:
            self.plotXY.mlab_source.scalars=zt
            self.plotXZ.mlab_source.scalars=yt
            self.plotYZ.mlab_source.scalars=xt
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex'), resizable=True)

    
    #import np,mayavi,testArrays
    #import mayavi.mlab
    #mayavi.mlab.clf()
    #iaList=[]
    #for i in range(4):
    #    x,y,z = np.mgrid[10*i:10+10*i:0.5,10*i:10+10*i:0.5,0:0.5:0.5]
    #    arr = testArrays.ab2D[:20,:20,None]
    #    s = mayavi.tools.pipeline.scalar_field(x,y,z,arr)
    #    ia = mayavi.mlab.pipeline.image_plane_widget(s,plane_orientation='z_axes')

class ArrayView4DTriBlob(HasTraits):
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

    tindex = Range(low='low', high='tlength', value=1, exclude_high=False, mode='slider') # or spinner
    zindex = Range(low='low', high='zlength', value=1, exclude_high=False, mode='slider')
    yindex = Range(low='low', high='ylength', value=1, exclude_high=False, mode='slider')
    xindex = Range(low='low', high='xlength', value=1, exclude_high=False, mode='slider')
    flip = Bool(False)
    
    arr = Array(shape=[None]*4)
    
    scene = Instance(MlabSceneModel, ())
    plot = Instance(PipelineBase)
    
    @on_trait_change('xindex,yindex,zindex,tindex')
    def update_plot(self):
        arr = self.arr
        print self.xindex, self.yindex,self.zindex, self.tindex
        if not hasattr(self,'min'):
            self.min = arr.min()
            self.max = arr.max()
        
        buffer = 10
        arrExp = np.zeros([arr.shape[2]+arr.shape[1]+buffer,arr.shape[3]+arr.shape[1]+buffer],dtype=arr.dtype)
        xt = arr[self.tindex,:,:,self.xindex].T
        yt = arr[self.tindex,:,self.yindex]
        zt = arr[self.tindex,self.zindex]
        arr_min = min(xt.min(),yt.min,zt.min())
        arr_max = max(xt.max(),yt.max(),zt.max())

        arrExp[-arr.shape[2]:,-arr.shape[3]:] = zt
        arrExp[-arr.shape[2]:,:arr.shape[1]] = xt
        arrExp[:arr.shape[1],-arr.shape[3]:] = yt
        #if self.flip:
        #    arrExp = arrExp.T
        # might be better to set the view here instead...
        
        if self.plot is None:
            self.plot = self.scene.mlab.imshow( arrExp, colormap='gray', vmin=arr.min(), vmax=arr.max())
        else:
            self.plot.mlab_source.set(scalars=arrExp)
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex'), resizable=True)

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
    arr1 = GTL.LoadMonolithic('/home/mashbudn/Documents/VIIBRE--ScarHealing/ActiveData/Resille/2012-04-11/1/Riselle_t1.TIF')
    arr2 = GTL.LoadMonolithic('/home/mashbudn/Documents/VIIBRE--ScarHealing/ActiveData/Resille/2012-04-11/1/Riselle_t2.TIF')
    arr3 = GTL.LoadMonolithic('/home/mashbudn/Documents/VIIBRE--ScarHealing/ActiveData/Resille/2012-04-11/1/Riselle_t3.TIF')
    
    a = ArrayViewTriIPWs(arr=np.array([arr1,arr2,arr3]))
    a.update_plot()
    a.configure_traits()
