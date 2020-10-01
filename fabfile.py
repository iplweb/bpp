from time import time

from fabric import task


@task
def installdb(c, db_name="bpp", fn="dump.psql"):
    c.local(f"/opt/local/bin/dropdb -U postgres {db_name} || true")
    c.local(f"/opt/local/bin/pg_restore -U postgres -j 6  -C -d template1 {fn}")
    c.local(f"python src/manage.py migrate")


@task
def getdb(c, db_name="bpp", fn="dump.psql"):
    c.sudo(f"pg_dump -Fc {db_name} > /tmp/{fn}", user="postgres")
    c.get(f"/tmp/{fn}")
    c.run(f"rm /tmp/{fn}")

    installdb(c, db_name, fn)


@task
def putdb(c, db_name="bpp", fn="dump.psql"):
    c.local(f"/opt/local/bin/pg_dump -U postgres -Fc {db_name} > /tmp/{fn}")
    c.put(f"/tmp/{fn}")

    c.sudo(f"supervisorctl stop all")
    c.sudo(f"pg_dump -Fc {db_name} > backup-{time()}.fabfile.sql", user="postgres")
    c.sudo(f"dropdb {db_name}", user="postgres")
    c.sudo(f"pg_restore -j 6 -C -d template1 {fn}", user="postgres")
    c.sudo(f"supervisorctl start all")
    c.local(f"rm /tmp/{fn}")


@task
def recreate_venv(c, user_name="bpp"):
    c.sudo(
        f"cd /home/{user_name} && rm -rf env", user=user_name, pty=True,
    )
    c.sudo(
        f"cd /home/{user_name} && virtualenv env -p/usr/bin/python3",
        user=user_name,
        pty=True,
    )
    c.sudo(
        f"cd /home/{user_name} && source env/bin/activate && pip install --upgrade --pre bpp-iplweb",
        user=user_name,
        pty=True,
    )
