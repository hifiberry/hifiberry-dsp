#!/bin/sh -e

### Exit, if not enough free space
requiredSpaceInMB=25
availableSpaceInMB=$(/bin/df -m /dev/mmcblk0p2 | awk 'NR==2 { print $4 }')
if [[ $availableSpaceInMB -le $requiredSpaceInMB ]]; then
    >&2 echo "Not enough free space"
    >&2 echo "Increase SD-Card size: Main Page > Additional functions > Resize FS"
    exit 1
fi

### Abort, if piCoreCDSP extension is already installed
if [ -f "/etc/sysconfig/tcedir/optional/HifiBerryDSP.tcz" ]; then
    >&2 echo "Uninstall the HifiBerryDSP Extension and reboot, before installing it again"
    >&2 echo "In Main Page > Extensions > Installed > select 'HifiBerry.tcz' and press 'Delete'"
    exit 1
fi


if [ -d "/tmp/hbdsp" ]; then
    #>&2 echo "Reboot before running the script again."
    #exit 1
    rm -rf /tmp/hbdsp
fi
mkdir -p /tmp/hbdsp

# Installs a module from the piCorePlayer repository - if not already installed.
# Call like this: install_if_missing module_name
install_if_missing(){
  if ! tce-status -i | grep -q "$1" ; then
    pcp-load -wil "$1"
  fi
}

# Installs a module from the piCorePlayer repository, at least until the next reboot - if not already installed.
# Call like this: install_temporarily_if_missing module_name
install_temporarily_if_missing(){
  if ! tce-status -i | grep -q "$1" ; then
    pcp-load -wil -t /tmp "$1" # Downloads to /tmp/optional and loads extensions temporarily
  fi
}

set -v

### Create hifiberry data folder

cd /mnt/mmcblk0p2/tce
[ -d hifiberry ] || mkdir hifiberry
mkdir -p /tmp/hbdsp/var/lib
ln -s /mnt/mmcblk0p2/tce/hifiberry /tmp/hbdsp/var/lib/hifiberry

install_if_missing python3.11
install_if_missing libxslt-dev
install_if_missing libxml2-dev
install_temporarily_if_missing python3.11-pip
install_temporarily_if_missing python3.11-wheel
install_temporarily_if_missing python3.11-dev
install_temporarily_if_missing binutils
install_temporarily_if_missing git
install_temporarily_if_missing compiletc
install_temporarily_if_missing libasound-dev

cd /tmp

### Install HifiBerryDSP
mkdir -p /usr/local/hifiberry
python3.11 -m venv /usr/local/hifiberry/environment
cd /usr/local/hifiberry/
(tr -d '\r' < environment/bin/activate) > environment/bin/activate_new # Create fixed version of the activate script. See https://stackoverflow.com/a/44446239
mv -f environment/bin/activate_new environment/bin/activate
source environment/bin/activate # activate custom python environment
python3 -m pip install --upgrade pip
# pypi versions are yanked, installing from git repository
git clone https://github.com/hifiberry/hifiberry-dsp.git /tmp/hifiberry-dsp
cd /tmp/hifiberry-dsp
python3.11 -m pip install .
deactivate # deactivate custom python environment
mkdir -p /tmp/hbdsp/usr/local/bin
cp -Rv /usr/local/hifiberry /tmp/hbdsp/usr/local
#create executables
ln -s /usr/local/hifiberry/environment/bin/dsptoolkit /tmp/hbdsp/usr/local/bin
ln -s /usr/local/hifiberry/environment/bin/sigmatcpserver /tmp/hbdsp/usr/local/bin

mkdir -p /tmp/hbdsp/usr/local/etc/init.d
echo "#!/bin/sh
# Version: 1.1.0

PNAME='sigmatcpserver'
DESC='SigmaTCP Server for HiFiBerry DSP'
PIDFILE=/var/run/sigmatcpserver/sigmatcpserver.pid

# Set DAEMON to the actual binary
DAEMON=\"/usr/local/hifiberry/environment/bin/sigmatcpserver\"

case \"\$1\" in
        start)
                echo \"Starting \$DESC...\"
                if [ -e \$PIDFILE ]; then
                        rm \$PIDFILE
                fi

                start-stop-daemon --start --quiet --exec \$DAEMON \
                        -- --daemon 
        ;;
        stop)
                echo \"Stopping \$DESC...\"
                start-stop-daemon --stop --quiet --exec \$DAEMON

        ;;
        restart)
                echo \"Restarting \$DESC...\"
                \$0 stop
                sleep 1
                \$0 start
        ;;
        status)
                # Check if sigmatcpserver daemon is running
                PID=\$(pgrep \$DAEMON)
                if [ 0\$PID -gt 0 ]; then
                        echo \"\$PNAME is running.\"
                        exit 0
                else
                        echo \"\$PNAME not running.\"
                        exit 1
                fi
        ;;
        *)
                echo
                echo -e \"Usage: \$0 [start|stop|restart|status]\"
                echo
                exit 1
        ;;
esac

exit 0" > /tmp/hbdsp/usr/local/etc/init.d/sigmatcpserver
chmod 755 /tmp/hbdsp/usr/local/etc/init.d/sigmatcpserver

mkdir -p /tmp/hbdsp/usr/local/tce.installed
echo "#!/bin/sh

/usr/local/etc.init.d/sigmatcpserver start
" >> /tmp/hbdsp/usr/local/tce.installed/HifiBerryDSP
### Create and install HifiBerryDSP.tcz

install_temporarily_if_missing squashfs-tools
mksquashfs /tmp/hbdsp /etc/sysconfig/tcedir/optional/HifiBerryDSP.tcz
echo "python3.11.tcz" > /etc/sysconfig/tcedir/optional/HifiBerryDSP.tcz.dep
echo "libxslt-dev.tcz" > /etc/sysconfig/tcedir/optional/HifiBerryDSP.tcz.dep
echo "libxml2-dev.tcz" > /etc/sysconfig/tcedir/optional/HifiBerryDSP.tcz.dep
echo HifiBerryDSP.tcz >> /etc/sysconfig/tcedir/onboot.lst

### Save Changes

pcp backup
pcp reboot
