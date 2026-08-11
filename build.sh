#!/bin/bash

# HiFiBerry DSP Toolkit - Build Script
# This script builds the Debian package

set -e  # Exit on any error

echo "Building HiFiBerry Toolkit Debian package..."

# Check if we're in the right directory
if [ ! -f "debian/control" ]; then
    echo "Error: debian/control not found. Please run this script from the package root directory."
    exit 1
fi

# Check if DIST is set by environment variable
if [ -n "$DIST" ]; then
    echo "Using distribution from DIST environment variable: $DIST"
    DIST_ARG="--dist=$DIST"
else
    echo "No DIST environment variable set, using sbuild default"
    DIST_ARG=""
fi

# Build the package
echo "Building package with sbuild..."
sbuild --chroot-mode=unshare \
       --no-clean-source \
       --enable-network $DIST_ARG
