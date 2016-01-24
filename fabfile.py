"""Szybkie interakcje z hostem 'master'
"""

from fabric.api import *

if not env['hosts']:
    env['hosts'] = ['vagrant@bpp-master']
    env['password'] = 'vagrant'

env['shell'] = "/bin/bash -l -i -c" 

env['db'] = 'bpp'
env['dbuser'] = 'bpp'

def prepare():
    run("django-bpp/buildscripts/prepare-build-env.sh")

def test():
    run("django-bpp/buildscripts/run-tests.sh")

def build():
    run("django-bpp/buildscripts/build-release.sh")

def migrate():
    run("python django-bpp/src/manage.py migrate")

def collectstatic():
    run("python django-bpp/src/manage.py collectstatic --noinput -v 0 ")

def venv():
    run("rm -rf env")
    run("/vagrant/provisioning/venv.sh")

def wheels():
    run("django-bpp/provisioning/wheels.sh")

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
    run("for app in password_policies celeryui menu dashboard multiseek messages_extends; do python django-bpp/src/manage.py migrate $app --fake; done")
