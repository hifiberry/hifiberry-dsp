#!/bin/bash
#
# Script to create different profiles from a standard profile 
# and settings files
#
cd `dirname $0`
BASEDIR=`pwd`
cd sample_files/xml

DEFAULTPROFILE=4way-default.xml
PATH=$BASEDIR/bin:$PATH
PYTHONPATH=$BASEDIR:$PYTHONPATH

for f in dacdsp-default.xml dacdsp-noautomute.xml; do 
 cp $DEFAULTPROFILE $f
done

dsptoolkit store-settings ../settings/invert-mute.txt dacdsp-default.xml
dsptoolkit store-settings ../settings/no_automute.txt dacdsp-noautomute.xml

