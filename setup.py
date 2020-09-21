from setuptools import setup, find_packages

import hifiberrydsp

setup(name='hifiberrydsp',
      version=hifiberrydsp.__version__,
      description='HiFiBerry DSP toolkit',
      long_description='A collection of tools to configure HiFiBerry DSP boards and porogram them from SigmaStudio', 
      url='http://github.com/hifiberry/hifiberry-dsp',
      author='Daniel Matuschek',
      author_email='daniel@mhifiberry.com',
      license='MIT',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'Topic :: System :: Hardware :: Hardware Drivers',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5'
      ],
      packages=find_packages(),
      install_requires=['xmltodict', 'lxml',
                        'spidev', 'pyalsaaudio', 'requests', 'zeroconf',
                        'RPi.GPIO'],
      scripts=['bin/dsptoolkit',
               'bin/sigmatcpserver',
               'bin/mergeparameters',
               'bin/optimizer-client'],
      keywords='audio raspberrypi dsp',
      zip_safe=False)
