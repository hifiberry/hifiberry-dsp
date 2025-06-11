#!/bin/bash
set -e

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

# Parse command-line arguments for version suffix
VERSION_SUFFIX=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --version-suffix=*)
      VERSION_SUFFIX="${1#*=}"
      shift
      ;;
    *)
      echo "Unknown option $1"
      shift
      ;;
  esac
done

echo "Building HiFiBerry DSP package..."
if [ -n "$VERSION_SUFFIX" ]; then
  echo "Using version suffix: $VERSION_SUFFIX"
fi

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

# Step 6: Copy Debian control files with proper formatting
echo "Copying and preparing Debian control files..."
# Ensure control file has Unix line endings
sed -i 's/\r$//' debian/control
cp debian/control debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/

# Process script files with special care
for script in postinst prerm; do
  echo "Processing $script script..."
  # First, ensure Unix line endings (remove any Windows CR characters)
  sed -i 's/\r$//' debian/$script
  
  # Ensure first line is a proper shebang
  if ! grep -q "^#!/bin/sh" debian/$script; then
    echo "Adding shebang to $script"
    sed -i '1s/^/#!/bin/sh\n/' debian/$script
  fi
  
  # Copy to package directory
  cp debian/$script debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/
  
  # Ensure script has executable permissions (0755)
  chmod 755 debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/$script
  
  # Extra verification
  echo "Verifying $script is executable"
  if [ ! -x debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/$script ]; then
    echo "Warning: $script is not marked as executable!"
    ls -la debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/$script
  fi
done

# Step 7: Update version in control file
VERSION=$(cd src && python3 -c 'from hifiberrydsp import __version__; print(__version__)')
if [ -n "$VERSION_SUFFIX" ]; then
  VERSION="${VERSION}${VERSION_SUFFIX}"
fi
sed -i "s/^Version:.*/Version: $VERSION/" debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/control

# Step 8: Build the Debian package
echo "Building Debian package..."
dpkg-deb --build debian/CONTENTS/python3-hifiberry-dsp .

echo "Done! The Debian package has been created."

