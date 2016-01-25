#!/bin/bash

apt-get install -y mc emacs24-nox links
su vagrant -c "echo alias\ jed=emacs24-nox >> ~/.bashrc"
