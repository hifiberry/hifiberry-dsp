Controlling remote servers
==========================

The dsptoolkit client tool can not just be used with a local server, but also with other systems 
on the network. It uses port TCP port 8089 to communicate with local and remote instances.

You can list instances running on the local network:

```
dsptoolkit servers
Looking for devices
raspberrypi._sigmatcp._tcp.local.: 192.168.99.7:8086 (version 0.11)
```

To control a remote server, just use the "--host" command line argument:

```
dsptoolkit --host 192.168.99.7 get-volume
Volume: 1.0000 / 100% / 0db

dsptoolkit --host 192.168.99.7 set-volume 90%
Volume set to -5.998086942222054dB

dsptoolkit --host 192.168.99.7 get-volume
Volume: 0.5013 / 90% / -6db
```
