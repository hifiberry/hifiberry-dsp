#!/bin/sh
echo "Reseting DSP chip"
sudo gpio export 18 out
sudo gpio write 1 0
sudo gpio write 1 1
