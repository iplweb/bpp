#!/bin/bash 

apt-get update
apt-get install -y openjdk-7-jre-headless xvfb firefox libxss1 libappindicator1 libindicator7 unzip python-pip supervisor

# Hostname
echo "selenium" > /etc/hostname
hostname `cat /etc/hostname`

# Hosts
echo "# Moje hosty: " >> /etc/hosts
echo "192.168.111.1 thinkpad thinkpad.localnet" >> /etc/hosts
echo "10.0.2.2 gate" >> /etc/hosts
echo "192.168.111.100 master master.localnet  messaging-test.localnet messaging-test" >> /etc/hosts
echo "192.168.111.101 staging staging.localnet" >> /etc/hosts
echo "192.168.111.150 selenium selenium.localnet" >> /etc/hosts

# Setup wget to use proxy
export WGET="wget -e use_proxy=on -e http_proxy=$http_proxy -e https_proxy=$https_proxy --quiet"

# Get selenium server
$WGET http://selenium-release.storage.googleapis.com/2.48/selenium-server-standalone-2.48.2.jar

# Get chrome with webdirver
$WGET https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
dpkg -i google-chrome*.deb
apt-get install -f -y

$WGET -N http://chromedriver.storage.googleapis.com/2.20/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
chmod +x chromedriver

mv -f chromedriver /usr/local/share/chromedriver
ln -s /usr/local/share/chromedriver /usr/local/bin/chromedriver
ln -s /usr/local/share/chromedriver /usr/bin/chromedriver

tar -xjvf selenium-optimized-profile-firefox-43.0.4.tbz2