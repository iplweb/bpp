"""Szybkie interakcje z hostem 'master'
"""

import os
from fabric.api import *
from fabric.contrib.files import exists

if not env['hosts']:
    env['hosts'] = ['vagrant@bpp-master']
    env['password'] = 'vagrant'

env['shell'] = "/bin/bash -l -i -c" 

env['db'] = 'bpp'
env['dbuser'] = 'bpp'

def prepare():
    run("latest/buildscripts/prepare-build-env.sh")

def test():
    run("latest/buildscripts/run-tests.sh")

def build():
    run("latest/buildscripts/build-deps.sh")
    run("latest/buildscripts/build-src.sh")
    local("ls -lash releases; du -h releases")

def migrate():
    run("python latest/src/manage.py migrate")

def collectstatic():
    run("python latest/src/manage.py collectstatic --noinput -v 0 ")

def venv():
    run("rm -rf env")
    run("/vagrant/provisioning/venv.sh")

def wheels():
    run("latest/provisioning/wheels.sh")

def vcs():
    with cd("django-bpp"):
        run("git pull")
        run("git reset --hard")

def download_db(restore=True, cleanup=False, recreate=True, download=True):
    """Download remote database dump.
    Restore dump on local host if 'restore' is True.
    Drop and recreate the target database if 'recreate' is True, remove dump
    file afterwards if 'remove' is also True.
    """
    if download is True:
        with settings(hide('stdout', 'running')):
            run('pg_dump --clean -F custom '
                '{0} > {0}.backup'.format(env.db))
        dump_file = get('{}.backup'.format(env.db), '%(host)s-%(path)s')[0]
    else:
        dump_file = '%s@%s-%s.backup' % (env.user, env.host, env.db)

    if not restore:
        return
    if recreate:
        with settings(warn_only=True):
            local('dropdb -U {0} {1}'.format(env.dbuser, env.db))
        local('createdb --echo --encoding=UTF8 '
              '-U postgres --owner={0} {1}'.format(env.dbuser, env.db))
    local('pg_restore -U postgres -d {1} {2}'.format(env.dbuser, env.db, dump_file))
    if cleanup:
        local('/bin/rm {}'.format(dump_file))

def django18_migrations_fix():
    run("for app in password_policies celeryui menu dashboard multiseek messages_extends; do python latest/src/manage.py migrate $app --fake; done")

def upload_deps(remote_os="Ubuntu-14.04", deps_version="20160124"):
    dn = "dependencies-%s-%s" % (remote_os, deps_version)
    fn = "%s.tar" % dn

    if not exists(dn):
        put("releases/%s" % fn, fn)
        run("tar -xf %s" % fn)
        run("rm %s" % fn)

def upload_src():
    latest = os.popen("python src/django_bpp/version.py").read()
    dn = "django-bpp-%s" % latest
    fn = "release-%s.tbz2" % latest
    if not exists(dn):
        put("releases/%s" % fn, fn)
        run("tar -xf %s" % fn)
        run("rm -rf latest %s" % fn)
        run("ln -s django-bpp-%s latest" % latest)

def upload():
    upload_deps()
    upload_src()

def upload_db(fn, db, dbuser):
    put(fn, fn)

    with settings(warn_only=True):
        run('dropdb -U {0} {1}'.format(dbuser, db))
    run('createdb --echo --encoding=UTF8 -U {0} --owner={0} {1}'.format(dbuser, db))
    run('pg_restore -U {0} -d {1} {2}'.format(dbuser, db, fn))
