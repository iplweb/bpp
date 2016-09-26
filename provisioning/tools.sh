#!/bin/bash

apt-get install -y mc emacs24-nox links
su $SUDO_USER -c "echo alias\ jed=emacs24-nox >> ~/.bashrc"
