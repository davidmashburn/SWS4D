from distutils.core import setup

# Read the version number
with open("SWS4D/_version.py") as f:
    exec(f.read())

setup(
    name='SWS4D',
    version=__version__, # use the same version that's in _version.py
    author='David N. Mashburn',
    author_email='david.n.mashburn@gmail.com',
    packages=['SWS4D'],
    scripts=[],
    url='NONE',
    license='LICENSE.txt',
    description='',
    long_description=open('README.rst').read(),
    install_requires=[
                      #'wxPython>=2.8', # wxPython isn't being found correctly by setuptools -- please install it manually!
                      'numpy>=1.0',
                      'scipy>=0.8',
                      'matplotlib>=1.0',
                      'traits>=4.0',
                      'traitsui>=4.0',
                      'mayavi>=4.0',
                      'mahotas>=0.5'
                      'FilenameSort>=0.1',
                      'GifTiffLoader>=0.1.6',
                      'np_utils>=0.3.3',
                      'coo_utils>=0.1',
                     ],
)
