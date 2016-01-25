#!/bin/bash
#
# Extra swap - 512MB
#

dd if=/dev/zero of=/swapfile bs=1M count=512
mkswap /swapfile
swapon /swapfile

echo swapon /swapfile > /etc/rc.local
echo exit 0 >> /etc/rc.local
