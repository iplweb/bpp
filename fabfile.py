"""Szybkie interakcje z hostem 'master'
"""

import os
from fabric.api import *
from fabric.contrib.files import exists

if not env['hosts']:
    env['hosts'] = ['ubuntu@bpp-master']

if not env.key_filename:
    env.key_filename = []
    for host in env['hosts']:
        hostname = host.replace("ubuntu@", "").replace("bpp-", "")
        fn = '.vagrant/machines/%s/virtualbox/private_key' % hostname
        try:
            stat = os.stat(fn)
        except OSError:
            continue
        env.key_filename.append(fn)


env['shell'] = "/bin/bash -l -i -c" 

env['db'] = 'bpp'
env['dbuser'] = 'bpp'

def prepare():
    run("latest/buildscripts/prepare-build-env.sh")

def build_assets():
    run("latest/buildscripts/build-js-css-html.sh")

def test(no_rebuild=False, no_django=False, no_pytest=False, no_qunit=False):
    opts = []
    if no_rebuild:
        opts.append("--no-rebuild")
    if no_django:
        opts.append("--no-django")
    if no_qunit:
        opts.append("--no-qunit")
    if no_pytest:
        opts.append("--no-pytest")
    run("latest/buildscripts/run-tests.sh %s" % " ".join(opts))

def build():
    run("/vagrant/buildscripts/build-wheel.sh")

def migrate():
    run("bpp-manage.py migrate")

def changepassword(user='admin'):
    run("bpp-manage.py changepassword %s" % user)

def collectstatic():
    run("python latest/src/manage.py collectstatic --noinput -v 0 ")

def venv():
    run("rm -rf env")
    run("/vagrant/provisioning/venv.sh")

def wheels():
    with cd("/vagrant/"):
        run("pip --quiet install -r requirements_dev.txt -r requirements.txt")

def vcs(branch=None):
    with cd("django-bpp"):
        run("git reset --hard")
        run("git pull")
        if branch:
            run("git checkout %s" % branch)
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

    sudo('supervisorctl stop all')
    with settings(warn_only=True):
        run('dropdb -U {0} {1}'.format(dbuser, db))
    with settings(warn_only=True):
        run('createuser -s bpp')
    run('createdb --echo --encoding=UTF8 -U {0} --owner={0} {1}'.format(dbuser, db))
    run('pg_restore -U {0} -d {1} {2}'.format(dbuser, db, fn))
    run('bpp-manage.py migrate')
    sudo('supervisorctl start all')
