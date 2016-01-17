#!/bin/sh

apt-get update
apt-get install -y tightvncserver olvwm

# Default VNC password:
su vagrant -c "mkdir ~/.vnc ; echo foobar | vncpasswd -f > ~/.vnc/passwd ; chmod 600 ~/.vnc/passwd"

# Start Xtightvnc on boot
echo "@reboot Xtightvnc -geometry 1200x900 :99" > mycron
echo "@reboot sleep 5 && olvwm -display :99" >> mycron
crontab -u vagrant mycron