from distutils.core import setup

setup(
    name='SWS4D',
    version='0.2.1.1',
    author='David N. Mashburn',
    author_email='david.n.mashburn@gmail.com',
    packages=['SWS4D'],
    scripts=[],
    url='NONE',
    license='LICENSE.txt',
    description='',
    long_description=open('README.rst').read(),
    install_requires=[
                      'wxPython>=2.8',
                      'numpy>=1.0',
                      'scipy>=0.8',
                      'matplotlib>=1.0',
                      'traits>=4.0',
                      'traitsui>=4.0',
                      'mayavi>=4.0',
                      'mahotas>=0.5'
                      'cmpGen>=0.1',
                      'FilenameSort>=0.1',
                      'GifTiffLoader>=0.1',
                      'np_utils>=0.1',
                      'coo_utils>=0.1',
                     ],
)
