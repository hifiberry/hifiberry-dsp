#!/bin/bash
set -e

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

# Step 1: Clean up any previous builds
echo "Cleaning up previous builds..."
rm -rf build/ dist/ *.egg-info/
rm -rf debian/CONTENTS
mkdir -p debian/CONTENTS

# Step 2: Build Python package
echo "Building Python package..."
cd src
python3 setup.py sdist
python3 setup.py egg_info
cd ..

# Step 3: Prepare for Debian packaging
echo "Preparing for Debian packaging..."
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/usr/share/hifiberry-dsp/systemd
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/DEBIAN
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system

# Step 4: Install Python package into Debian structure
echo "Installing Python package..."
cd src
python3 setup.py install --root=../debian/CONTENTS/python3-hifiberry-dsp --install-layout=deb
cd ..

# Step 5: Copy systemd service file
echo "Copying systemd service file..."
cp systemd/sigmatcpserver.service debian/CONTENTS/python3-hifiberry-dsp/usr/share/hifiberry-dsp/systemd/
cp systemd/sigmatcpserver.service debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/

# Step 6: Copy Debian control files
echo "Copying Debian control files..."
cp debian/control debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/
cp debian/postinst debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/
cp debian/prerm debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/
chmod 755 debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/postinst
chmod 755 debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/prerm

# Step 7: Update version in control file
VERSION=$(cd src && python3 -c 'from hifiberrydsp import __version__; print(__version__)')
sed -i "s/^Version:.*/Version: $VERSION/" debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/control

# Step 8: Build the Debian package
echo "Building Debian package..."
dpkg-deb --build debian/CONTENTS/python3-hifiberry-dsp .

echo "Done! The Debian package has been created."

