import sys
from setuptools import setup, find_packages
from setuptools.command.install import install
import os

class CustomInstall(install):
    """Custom install command to handle systemd service installation."""
    def run(self):
        # Run the standard installation
        install.run(self)

        # Define source and destination paths for the systemd unit file
        unit_file_src = os.path.join(os.path.dirname(__file__), 'debian', 'lib', 'systemd', 'system', 'sigmatcpserver.service')
        unit_file_dest = '/lib/systemd/system/sigmatcpserver.service'

        # Install the systemd unit file
        print(f"Installing systemd unit file from {unit_file_src} to {unit_file_dest}...")
        if os.path.exists(unit_file_src):
            os.system(f"sudo cp {unit_file_src} {unit_file_dest}")
            os.system("sudo systemctl daemon-reload")
            os.system("sudo systemctl enable sigmatcpserver.service")
            print("Systemd unit file installed and service enabled.")
        else:
            print(f"Error: Systemd unit file not found at {unit_file_src}. Skipping installation.")

# Main setup configuration
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
                        'waitress'
                        'requests'],
      scripts=['bin/dsptoolkit',
               'bin/sigmatcpserver',
               'bin/mergeparameters',
               'bin/optimizer-client',
               'bin/spdifclockgen',
               'bin/dsp-metadata-server'],

      keywords='audio raspberrypi dsp',
      zip_safe=False)
