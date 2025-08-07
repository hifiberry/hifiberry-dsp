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
if [ ! -f systemd/sigmatcpserver.service ]; then
    echo "ERROR: systemd/sigmatcpserver.service not found!"
    exit 1
fi

# Ensure target directories exist
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/usr/share/hifiberry-dsp/systemd
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system

# Copy the service file
cp systemd/sigmatcpserver.service debian/CONTENTS/python3-hifiberry-dsp/usr/share/hifiberry-dsp/systemd/
cp systemd/sigmatcpserver.service debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/

# Set proper permissions for systemd service file
chmod 644 debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/sigmatcpserver.service

# Verify the service file was copied correctly
if [ -f debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/sigmatcpserver.service ]; then
    echo "✓ Systemd service file copied to package"
    ls -la debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/sigmatcpserver.service
    echo "Content check:"
    head -5 debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/sigmatcpserver.service
else
    echo "ERROR: Failed to copy systemd service file to package!"
    exit 1
fi

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
  else
    echo "✓ $script is properly executable"
  fi
done

# Verify all required files are in place for systemd service installation
echo "Verifying package contents for systemd service..."
echo "Checking for systemd service file:"
ls -la debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/sigmatcpserver.service || echo "ERROR: systemd service file missing!"
echo "Checking for postinst script:"
ls -la debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/postinst || echo "ERROR: postinst script missing!"

# Step 7: Update version in control file
VERSION=$(cd src && python3 -c 'from hifiberrydsp import __version__; print(__version__)')
if [ -n "$VERSION_SUFFIX" ]; then
  VERSION="${VERSION}${VERSION_SUFFIX}"
fi
sed -i "s/^Version:.*/Version: $VERSION/" debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/control

# Step 8: Build the Debian package
echo "Building Debian package..."
dpkg-deb --build debian/CONTENTS/python3-hifiberry-dsp .

# Verify the package contains the systemd service file
echo "Verifying package contents..."
if command -v dpkg-deb >/dev/null 2>&1; then
    echo "Checking if systemd service file is in the package:"
    dpkg-deb -c python3-hifiberry-dsp_*.deb | grep sigmatcpserver.service || echo "WARNING: systemd service file not found in package!"
fi

echo "Done! The Debian package has been created."

