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

class ArrayViewTriIPW(HasTraits):
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
    yindex = Range(low='low', high='ylength', value=20, exclude_high=False, mode='slider')
    xindex = Range(low='low', high='xlength', value=100, exclude_high=False, mode='slider')
    flip = Bool(False)
    
    arr = Array(shape=[None]*4)
    
    scene = Instance(MlabSceneModel, ())
    
    plotXY = Instance(PipelineBase)
    plotXZ = Instance(PipelineBase)
    plotYZ = Instance(PipelineBase)
    
    # Completely unnecessary
    def __init__(self,arr,**traits):
        super(self.__class__,self).__init__(arr=arr.transpose(0,1,3,2)[:,:,:,::-1],**traits) # Call __init__ on the super
    
    @on_trait_change('scene.activated')
    def display_scene(self):
        # Interaction properties can only be changed after the scene
        # has been created, and thus the interactor exists
        #self.scene.scene.background = (0, 0, 0)
        self.scene.scene.interactor.interactor_style = tvtk.InteractorStyleImage()
        #self.scene.scene.parallel_projection = True
        # self.scene3d.mlab.view(40, 50)
        
        print self.xindex, self.yindex,self.zindex, self.tindex
        
        if not hasattr(self,'min'):
            self.min = self.arr.min()
            self.max = self.arr.max()
        
        self.plotBuffer = plotbuf = 10
        self.zscale = zsc = 2.6
        
        xs,ys,zs = self.arr.shape[3], self.arr.shape[2], self.arr.shape[1]
        
        xt = self.arr[self.tindex,:,:,self.xindex].T
        yt = self.arr[self.tindex,:,self.yindex]
        zt = self.arr[self.tindex,self.zindex]
        
        # Make simple image actors instead of image plane widgets
        #x,y = np.ogrid[:ys,:xs]
        #sXY = self.scene.mlab.pipeline.array2d_source(x,y,zt)
        #x,y = np.ogrid[ ys+plotbuf : ys+plotbuf+zsc*zs : zsc  ,  :xs ] # right
        ##x,y = np.ogrid[ -zsc*zs-plotbuf:1-plotbuf:zsc  ,  :xs ] # left
        #sXZ = self.scene.mlab.pipeline.array2d_source(x,y,yt)
        #x,y = np.ogrid[ :ys  ,  xs+plotbuf : xs+plotbuf+zsc*zs : zsc ] # top
        ##x,y = np.ogrid[ :ys  ,  -zsc*zs-plotbuf : 1-plotbuf : zsc ] # bottom
        #sYZ = self.scene.mlab.pipeline.array2d_source(x,y,xt)
        
        x,y,z = np.mgrid[:ys,:xs,:1]
        sXY = self.scene.mlab.pipeline.scalar_field(x,y,z,zt[:,:,None])
        x,y,z = np.mgrid[ ys+plotbuf : ys+plotbuf+zs*zsc : zsc  ,  :xs , :1 ] # right
        #x,y,z = np.ogrid[ -zsc*zs-plotbuf:1-plotbuf:zsc  ,  :xs , :1 ] # left
        sXZ = self.scene.mlab.pipeline.scalar_field(x,y,z,yt[:,:,None])
        x,y,z = np.mgrid[ :ys  ,  xs+plotbuf : xs+plotbuf+zsc*zs : zsc , :1 ] # top
        #x,y,z = np.ogrid[ :ys  ,  -zsc*zs-plotbuf:1-plotbuf:zsc , :1 ] # bottom
        sYZ = self.scene.mlab.pipeline.scalar_field(x,y,z,xt[:,:,None])
            
        for (s,pl) in [ (sXY,'plotXY') , (sXZ,'plotXZ') , (sYZ,'plotYZ')]:
            #setattr( self, pl, self.scene.mlab.pipeline.image_actor(s,interpolate=False, colormap='gray', vmin=arr.min(), vmax=arr.max()) )
            setattr( self, pl, self.scene.mlab.pipeline.image_plane_widget(s,plane_orientation='z_axes', colormap='gray', vmin=self.min, vmax=self.max) )
        
        for pl in [self.plotXY,self.plotXZ,self.plotYZ]:
            pl.ipw.left_button_action = 0
            #pl.ipw.interaction = 0
        
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
            return self.scene.mlab.plot3d( x, y, [0,0], [0,0], color=(0, 0, 0), tube_radius=3 )
        
        self.cursor_y  = quickLine( self.yindex, [0,plotbuf+xs+zs*zsc] )
        self.cursor_x  = quickLine( [0,plotbuf+ys+zs*zsc], self.xindex )
        
        self.cursor_zy = quickLine( [0,ys], plotbuf+xs+self.zindex*zsc )
        self.cursor_zx = quickLine( plotbuf+ys+self.zindex*zsc, [0,xs] )
    
    @on_trait_change('tindex')
    def update_all_plots(self):
        if self.plotXY is not None:
            self.plotXY.mlab_source.scalars = self.arr[self.tindex,self.zindex]
            self.plotXZ.mlab_source.scalars = self.arr[self.tindex,:,self.yindex,:]
            self.plotYZ.mlab_source.scalars = self.arr[self.tindex,:,:,self.xindex].T
    
    @on_trait_change('xindex')
    def update_x_plots(self):
        if self.plotXY is not None:
            self.plotYZ.mlab_source.scalars = self.arr[self.tindex,:,:,self.xindex].T
            self.cursor_x.mlab_source.set( y=[self.xindex]*2 )
    @on_trait_change('yindex')
    def update_y_plots(self):
        if self.plotXY is not None:
            self.plotXZ.mlab_source.scalars = self.arr[self.tindex,:,self.yindex,:]
            self.cursor_y.mlab_source.set( x=[self.yindex]*2 )
    @on_trait_change('zindex')
    def update_z_plots(self):
        if self.plotXY is not None:
            xs,ys = self.arr.shape[3],self.arr.shape[2]
            self.plotXY.mlab_source.scalars = self.arr[self.tindex,self.zindex]
            self.cursor_zy.mlab_source.set( y=[self.plotBuffer+xs+self.zindex*self.zscale]*2 )
            self.cursor_zx.mlab_source.set( x=[self.plotBuffer+ys+self.zindex*self.zscale]*2 )
    
    # The layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene), height=250, width=300, show_label=False),
                Group('xindex','yindex','zindex', 'tindex'), resizable=True)

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
    numLoad=1
    name = '/media/home/ViibreData/ActiveData/NewSegmentation/AS Edge Wound Healing/2009SEPT24CellCycle05_W2X/','','2009SEPT24Cell_Cycle05_2X20s.tif'
    #name = '/home/mashbudn/Documents/VIIBRE--ScarHealing/ActiveData/Resille/2012-04-11/1/Riselle_t','1','.TIF'
    arr0 = GTL.LoadMonolithic(''.join(name))
    arr = np.zeros([numLoad]+list(arr0.shape),dtype=arr0.dtype)
    arr[0] = arr0
    for i in range(1,numLoad):
        arr[i]= GTL.LoadMonolithic(name[0]+str(i+1)+name[2])
    
    a = ArrayViewTriIPW(arr=arr)
    a.configure_traits()
