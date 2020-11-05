# Resetting the DSP

The DSP's reset is connected to Pi's GPIO 17. To reset the DSP, you need to first pull this to LOW, then to HIGH:

```
echo 17 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio17/direction
echo 0 > /sys/class/gpio/gpio17/value
echo 1 > /sys/class/gpio/gpio17/value
```
