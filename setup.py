from setuptools import setup, find_packages

import hifiberrydsp

with open("README", "r") as fh:
    long_description = fh.read()

setup(name='hifiberrydsp',
      version=hifiberrydsp.__version__,
      description='A DSP Toolkit',
      long_description=long_description,
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
                        'spidev', 'pyalsaaudio', 'zeroconf',
                        'RPi.GPIO'],
      scripts=['bin/dsptoolkit',
               'bin/sigmatcpserver',
               'bin/mergeparameters',
               'bin/optimizer-client'],
      keywords='audio raspberrypi dsp',
      zip_safe=False)
