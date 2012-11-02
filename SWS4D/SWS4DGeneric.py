import wx
import numpy as np
import scipy.ndimage
import GifTiffLoader as GTL
from SWS4D import SeedWaterSegmenter4D

app=wx.App()

# Good place to start...
d = wx.DirSelector('Choose the directory of a 4D stack')

te=wx.TextEntryDialog(None,'Please input the z aspect for this data set (usually 2-3)')
dia=te.ShowModal()
if dia==wx.ID_CANCEL:
    exit()
elif dia==wx.ID_OK:
    try:     zscale = float(te.GetValue())
    except:  exit()

wildcard = '*.[gtTG][iI][fF]' # match and .gif or .tif (but not .tiff, sadly...oh well...)

shape = GTL.GetShape(GTL.getSortedListOfFiles(d,wildcard)[0])

if len(shape)==2:
    arr = GTL.LoadSequence4D(d,wildcard)
else:
    arr = GTL.LoadMonolithicSequence4D(d,wildcard)

# This (and the xy/z resolutions) would be a really good reason for an input file in the folder with the data and/or the save info!
# I could even have an input format that stored the name of the last save file and the directory of the stack... sounds like the way compucell and the like do it actually...
arr = scipy.ndimage.gaussian_filter(arr,sigma=[0, 1./zscale, 1., 1.])

sws4d=SeedWaterSegmenter4D(arr=arr,cursorSize=0.5,displayString=d)#,loadfile=f)
sws4d.configure_traits()

