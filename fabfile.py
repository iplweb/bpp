from fabric.api import *

env['hosts'] = ['vagrant@bpp-master']
env['password'] = 'vagrant'
env['shell'] = "/bin/bash -l -i -c" 

def wheels():
    run("django-bpp/provisioning/wheels.sh")

def prepare():
    run("django-bpp/buildscripts/prepare-build-env.sh")

def test():
    run("django-bpp/buildscripts/run-tests.sh")

def build():
    run("django-bpp/buildscripts/build-release.sh")

def vcs():
    with cd("django-bpp"):
        run("git pull")
