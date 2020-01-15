#!/bin/bash
#
# Some simple tests
#
cd `dirname $0`
BASEDIR=`pwd`
PATH=$BASEDIR/bin:$PATH
export $PATH
PYTHONPATH=$BASEDIR:$PYTHONPATH
export PYTHONPATH

cp sample_files/xml/4way-default.xml tmp/test.xml

which dsptoolkit

for f in sample_files/settings/*; do
 dsptoolkit store-settings $f tmp/test.xml
done

