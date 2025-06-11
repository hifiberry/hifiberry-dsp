#!/bin/bash
set -e

echo "Building HiFiBerry DSP package using Docker for reproducible builds..."

# Get the project directory path
PROJECT_DIR=$(pwd)

# Create a temporary Dockerfile
cat > Dockerfile.build << EOF
FROM debian:buster-slim

# Install build and Python dependencies
RUN apt-get update && apt-get install -y \\
    python3 \\
    python3-dev \\
    python3-setuptools \\
    python3-pip \\
    python3-xmltodict \\
    python3-lxml \\
    python3-requests \\
    python3-flask \\
    python3-waitress \\
    python3-numpy \\
    build-essential \\
    libxml2-dev \\
    libxslt1-dev \\
    zlib1g-dev \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build
EOF

# Build the Docker image
echo "Building Docker image..."
docker build -t hifiberry-dsp-builder -f Dockerfile.build .

# Run the Docker container to perform the build
echo "Running build in Docker container..."
docker run --rm -v "$PROJECT_DIR:/build" hifiberry-dsp-builder /bin/bash -c "
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Step 1: Clean up any previous builds
echo 'Cleaning up previous builds...'
rm -rf build/ dist/ *.egg-info/
rm -rf debian/CONTENTS
mkdir -p debian/CONTENTS

# Step 2: Build Python package
echo 'Building Python package...'
cd src
python3 setup.py sdist
python3 setup.py egg_info
cd ..

# Step 3: Prepare for Debian packaging
echo 'Preparing for Debian packaging...'
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/usr/share/hifiberry-dsp/systemd
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/DEBIAN
mkdir -p debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system

# Step 4: Install Python package into Debian structure
echo 'Installing Python package...'
cd src
python3 setup.py install --root=../debian/CONTENTS/python3-hifiberry-dsp --install-layout=deb
cd ..

# Step 5: Copy systemd service file
echo 'Copying systemd service file...'
cp systemd/sigmatcpserver.service debian/CONTENTS/python3-hifiberry-dsp/usr/share/hifiberry-dsp/systemd/
cp systemd/sigmatcpserver.service debian/CONTENTS/python3-hifiberry-dsp/lib/systemd/system/

# Step 6: Copy Debian control files
echo 'Copying Debian control files...'
cp debian/control debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/
cp debian/postinst debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/
cp debian/prerm debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/
chmod 755 debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/postinst
chmod 755 debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/prerm

# Step 7: Update version in control file
VERSION=\$(cd src && python3 -c 'from hifiberrydsp import __version__; print(__version__)')
sed -i \"s/^Version:.*/Version: \$VERSION/\" debian/CONTENTS/python3-hifiberry-dsp/DEBIAN/control

# Step 8: Install dpkg-deb
apt-get update && apt-get install -y dpkg-dev

# Step 9: Build the Debian package
echo 'Building Debian package...'
dpkg-deb --build debian/CONTENTS/python3-hifiberry-dsp .

# Fix permissions to ensure user can access the created files
chown -R $(id -u):$(id -g) debian/CONTENTS
chown $(id -u):$(id -g) *.deb
"

# Clean up
echo "Cleaning up Docker build files..."
rm -f Dockerfile.build

echo "Done! The Debian package has been created in a reproducible environment."
