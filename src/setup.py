import sys
from setuptools import setup, find_packages
from hifiberrydsp import __version__ as hifiberrydsp_version
import os
import platform

# Main setup configuration
setup(name='hifiberry-dsp',
      version=hifiberrydsp_version,
      description='HiFiBerry DSP toolkit',
      long_description='A collection of tools to configure HiFiBerry DSP boards and program them from SigmaStudio',
      url='http://github.com/hifiberry/hifiberry-dsp',
      author='Daniel Matuschek',
      author_email='daniel@mhifiberry.com',
      license='MIT',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Developers',
          'Topic :: System :: Hardware :: Hardware Drivers',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.11',
          'Programming Language :: Python :: 3.12'
      ],
      packages=[
          'hifiberrydsp',
          'hifiberrydsp.hardware',
          'hifiberrydsp.server',
          'hifiberrydsp.client',
          'hifiberrydsp.parser',
          'hifiberrydsp.filtering',
          'hifiberrydsp.alsa',
          'hifiberrydsp.lg',
          'hifiberrydsp.api',
      ],
      install_requires=['xmltodict', 
                        'lxml',
                        'spidev', 
                        'pyalsaaudio', 
                        'requests',
                        'RPi.GPIO',
                        'flask',
                        'waitress',
                        'numpy'],
      python_requires='>=3.11',
      scripts=['bin/dsptoolkit',
               'bin/sigmatcpserver',
               'bin/dsp-install-profile',
               'bin/dsp-program-info',
               'bin/dsp-get-profile'],
      keywords='audio raspberrypi dsp',
      zip_safe=False,
)
