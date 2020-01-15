#!/bin/bash
#
# Script to create different profiles from a standard profile 
# and settings files
#
cd `dirname $0`
BASEDIR=`pwd`
cd sample_files/xml

DEFAULTPROFILE=4way-iir-delay-mixer.xml
PATH=$BASEDIR/bin:$PATH
PYTHONPATH=$BASEDIR:$PYTHONPATH

for f in dacdsp-default.xml dacdsp-noautomute.xml beocreate-default.xml; do 
 cp $DEFAULTPROFILE $f
done

dsptoolkit store-settings ../settings/invert-mute.txt dacdsp-default.xml
dsptoolkit store-settings ../settings/no_automute.txt dacdsp-noautomute.xml
dsptoolkit store-settings ../settings/beocreate-default.txt beocreate-default.xml

dsptoolkit store-settings ../settings/full-volume.txt dacdsp-default.xml
dsptoolkit store-settings ../settings/full-volume.txt dacdsp-noautomute.xml

