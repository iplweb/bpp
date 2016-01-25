#!/bin/bash -e

locale-gen pl_PL.UTF-8
update-locale pl_PL.UTF-8
echo LANG="pl_PL.UTF-8" > /etc/default/locale
