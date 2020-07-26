from fabric import task, Connection
import os


@task
def getdb(c, db_name="bpp", fn="dump.psql"):
    c.sudo(f"pg_dump -Fc {db_name} > /tmp/{fn}", user="postgres")
    c.get(f"/tmp/{fn}")
    c.run(f"rm /tmp/{fn}")

    c.local(f"/opt/local/bin/dropdb -U postgres {db_name} || true")
    c.local(f"/opt/local/bin/pg_restore -U postgres -j 6  -C -d template1 {fn}")
