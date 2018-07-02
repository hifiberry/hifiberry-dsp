from setuptools import setup, find_packages

setup(name='hifiberrydsp',
      version='0.1',
      description='A DSP Toolkit',
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
      scripts=['bin/dsptoolkit'],
      keywords='audio raspberrypi dsp',
      zip_safe=False)
