# -*- encoding: cp852 -*-

"""
Ten plik instaluje w nast©puj¥cej strukturze:

$HOME
    env.webapps_root (websites)/
        env.host (linux-dev)/
            bin/ \
            lib/  - stworzone przez mkvirtualenv
            etc/ /
            env.sources_dir (django-bpp)/ - «r¢dˆa (repo hg)

Komendy:
    install -- instaluje wszystko na czystym serwerze,
    deploy -- u¾ywaj po zmianach w «r¢dˆach
"""

import time

from fabric.api import env, run, get, put
from fabric.context_managers import settings, cd, prefix
from fabric.contrib.files import append, upload_template
from fabric.decorators import hosts, task
from fabric.operations import sudo, local


env.roledefs.update({
    'staging': ['dotz@linux-dev'],
    'production': ['zarzadca@bpp.umlub.pl'],
    'dbdump': ['dbdump@bpp.umlub.pl']
})

#env.hosts = [env.roledefs['production'][0], ]
#env.password = '93piecset5krowa'

#env.hosts = [env.roledefs['staging'][1]]
#env.password = 'foobar'

env.webapps_root = 'websites'
env.sources_dir = 'django-bpp'
env.DBNAME = 'django_bpp'

PORT_CONFIG = {
    'linux-dev': {
        'HTTPS_PORT': 443,
        'HTTP_PORT': 80
    },

    'bpp.umlub.pl': {
        'HTTPS_PORT': 9443,
        'HTTP_PORT': 9080
    }
}


def service(sn, cmd):
    sudo('service %s %s' % (sn, cmd))


def reload(sn):
    return service(sn, 'reload')


def stop(n):
    service(n, "stop")


def start(n):
    service(n, "start")


def restart(n):
    service(n, "restart")


@task
def server_init():
    """1. Inicjalizacja servera -- uruchom RAZ na pocz¥tku

    Instaluje pip, virtualenvwrapper, robi katalog 'websites', inicjalizuje
    w nim virtualenv oraz repozytorium hg."""
    append('.bash_profile', 'export WORKON_HOME=~/%s' % env.webapps_root)
    # mkvirtualenv sam sobie to zrobi
    # run("mkdir %s" % env.webapps_root)
    with settings(warn_only=True):
        sudo("apt-get remove --yes virtualenvwrapper")
    sudo("apt-get install --yes python-pip")
    sudo("pip install virtualenvwrapper")

    apt_packages_install()
    npm_packages_install()


@task
def postgresql_setup():
    with settings(warn_only=True):
        sudo('su - postgres -c "createuser -s %s"' % env.user)
        run("createdb %s" % env.DBNAME)
        run("createlang plpythonu %s" % env.DBNAME)


@task
def virtualenv_init():
    """2. Inicjalizacja virtualenv."""
    create_virtualenv()
    sudo("apt-get install --yes mercurial")
    hg_init()


@task
def install():
    "111AAA ==> Instaluje WSZYSTKO na czystym serwerze"
    server_init()
    virtualenv_init()
    deploy()
    with settings(warn_only=True):
        service('nginx', 'start')



@task
def npm_packages_install():
    sudo("npm -g install bower")

@task
def apt_packages_install():
    '''Instaluje pakiety DEB wymagane przez serwis.'''
    with cd(sources_path()):
        with settings(warn_only=True):
            sudo("apt-get install --yes `cat requirements.apt`")


virtualenvwrapper = lambda x=None: \
    prefix("source /usr/local/bin/virtualenvwrapper.sh")


def nickname(host):
    """Zwraca nickname hosta, czyli nazw© hosta bez kresek, kropek i minus¢w.
    """
    return host.replace(".", "_").replace("-", "_")


def settings_module():
    return "django_bpp.settings.hosts.%s" % nickname(env.host)


@task
def create_virtualenv():
    with virtualenvwrapper():
        run("mkvirtualenv --system-site-packages %s" % env.host)
        append(
            virtualenv_path() + '/bin/activate',
            'export DJANGO_SETTINGS_MODULE="%s"' % settings_module())
    virtualenv("pip install --upgrade pip setuptools")


@task
def virtualenv_packages_install():
    with cd(sources_path()):
        virtualenv(
            'pip install --use-wheel --no-index --find-links=wheelhouse '
            '-r requirements.pip')


def virtualenv_path():
    '''—cie¾ka do virtualenv.'''
    return '/home/' + env.user + '/' + env.webapps_root + '/' + env.host


def sources_path():
    '''—cie¾ka do «r¢deˆ w katalogu virtualenv.'''

    return virtualenv_path() + '/' + env.sources_dir


@task
def hg_init():
    with cd(virtualenv_path()):
        with settings(warn_only=True):
            run("mkdir %s" % env.sources_dir)
    local("hg clone . ssh://%s/%s" % (env.host_string, sources_path()))


def get_config():
    ret = dict(VIRTUALENV_HOST=env.host,
               VIRTUALENV_PATH=virtualenv_path(),
               VIRTUALENV_GUNICORN_PORT=9999,
               SOURCES_DIR=env.sources_dir,
               VIRTUALENV_NICK=nickname(env.host),
               UNIX_USER=env.user,
               SETTINGS=settings_module())
    ret.update(PORT_CONFIG[env.host])
    return ret

@task
def clean_pyc():
    with cd(sources_path()):
        with settings(warn_only=True):
            run("find . -name \*.pyc -print0 | xargs -0 rm -v ")

@task
def hg_push():
    """push && update"""
    with settings(warn_only=True):
        res = local("hg push --new-branch ssh://%s/%s" % (env.host_string, sources_path()),
                    capture=True)
        if res.return_code:
            if "no changes found" not in res:
                raise Exception(res.stdout + res.stderr)

    with cd(sources_path()):
        run("hg update")

    clean_pyc()

    upload_template(
        filename='conf/wsgi.py',
        destination=sources_path() + '/django_bpp/wsgi.py',
        context=get_config(),
        use_jinja=True, use_sudo=True, backup=False)


@task
def nginx_install():
    upload_template(
        filename='conf/nginx.conf',
        destination='/etc/nginx/sites-available/%s' % env.host,
        context=get_config(),
        use_jinja=True, use_sudo=True, backup=False)
    # Wygeneruj falszywy certyfikat

    with settings(warn_only=True):
        reload('nginx')


@task
def supervisor_install():
    upload_template(
        filename='conf/supervisord.conf',
        destination='/etc/supervisor/conf.d/%s.conf' % env.host,
        context=get_config(),
        use_jinja=True, use_sudo=True, backup=False)
    stop('supervisor')
    time.sleep(3)
    start('supervisor')
    time.sleep(3)
    service('supervisor', 'status')
    sudo("supervisorctl status")


@task
def nginx_enable():
    with settings(warn_only=True):
        sudo(
            "ln -s /etc/nginx/sites-available/%s /etc/nginx/sites-enabled/%s" % (
                env.host, env.host))
        reload('nginx')


@task
def nginx_disable():
    with settings(warn_only=True):
        sudo("rm /etc/nginx/sites-enabled/%s" % (env.host))
        reload('nginx')



@task
def update():
    """2. Wrzu† stron© na serwer (zr¢b wszystko, full service)."""
    hg_push()
    apt_packages_install()
    postgresql_setup()
    virtualenv_packages_install()
    nginx_install()
    nginx_enable()
    supervisor_install()
    collectstatic()
    upload_unaccent_rules()
    manage('migrate')


def supervisor(action):
    sudo("supervisorctl %s %s:*" % (action, env.host))


@task
def supervisor_restart():
    supervisor("restart %s:*" % env.host)


@task
def supervisor_stop():
    supervisor('stop')


@task
def supervisor_start():
    supervisor('start')


def virtualenv(cmd):
    with virtualenvwrapper():
        with prefix("workon %s" % env.host):
            run(cmd)


@task
def manage(cmd):
    virtualenv("%s/bin/python %s/manage.py %s" % (virtualenv_path(),
                                                  sources_path(),
                                                  cmd))


def venv_tests():
    manage("test bpp")


@task
def collectstatic():
    manage("bower_install -F")
    manage("collectstatic --noinput -c")


DUMP = "dump.gz"


@task
@hosts('dbdump@bpp.umlub.pl')
def download_dump():
    '''[dev] Pobierz dump bazodanowy z serwera bpp.umlub.pl'''
    run("pg_dump -U aml b_med | gzip > \"%s\"" % DUMP)
    get(DUMP)
    run("rm \"%s\"" % DUMP)


@task
def hg():
    local("hg push")
    local("fab hg_push")


@task
def push_db():
    local("pg_dump django_bpp | gzip > dump.gz")
    put("dump.gz")
    supervisor("stop")
    run("dropdb django_bpp")
    run("createdb django_bpp")
    run("zcat dump.gz | psql django_bpp")
    supervisor("start")


@task
def pkg(package):
    with settings(warn_only=True):
        local("rm wheelhouse/*%s*" % package)
    local("pip wheel %s" % package)


@task
def srcpkg(package):
    for line in open("requirements.src"):
        if line.find(package) >= 1:
            break

    repo, egg = line.strip().split("#egg=")
    with settings(warn_only=True):
        local("hg remove -f wheelhouse/*%s*" % egg)
        local("hg remove -f wheelhouse/*%s*" % egg.replace("-", "_"))
    local("pip wheel %s#egg=%s" % (repo, egg))
    with settings(warn_only=True):
        local("hg add wheelhouse/*%s*" % egg)
        local("hg add wheelhouse/*%s*" % egg.replace("-", "_"))
        local('hg commit -m "Added new version for %s" wheelhouse' % egg)

        local("pip uninstall --yes %s" % egg)
        local("pip install --use-wheel --no-index --find-links=wheelhouse %s" % egg)


@task
def rebuild_package(package):
    with cd(sources_path()):
        virtualenv("pip wheel %s" % package)
        run("hg add wheelhouse")


@task
def reinstall_package(package):
    hg_push()
    with cd(sources_path()):
        with settings(warn_only=True):
            virtualenv("pip uninstall --yes %s" % package)
        virtualenv(
            "pip install --use-wheel --no-index --upgrade --find-links=wheelhouse %s" % package)


@task
def upload_db():
    supervisor('stop')
    service('pgbouncer', 'stop')
    run("dropdb django_bpp")
    run("createdb django_bpp")
    run("gzcat -dc dump.gz | psql django_bpp")
    service('pgbouncer', 'start')
    supervisor('start')


@task
def upload_unaccent_rules():
    put('./postgresql-support/unaccent-rules.txt', '/usr/share/postgresql/9.3/tsearch_data/unaccent.rules', use_sudo=True)