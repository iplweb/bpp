#!/bin/sh

export PGUSER="${DJANGO_BPP_DB_USER}"
export PGHOST="${DJANGO_BPP_DB_HOST}"
export PGPASSWORD="${DJANGO_BPP_DB_PASSWORD}"

echo -n "Creating database ${DJANGO_BPP_DB_NAME}, if not exists... "
echo "SELECT 'CREATE DATABASE ${DJANGO_BPP_DB_NAME}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DJANGO_BPP_DB_NAME}')\gexec" | psql
echo "done."

echo -n "Copying staticroot to Docker volume... "
staticroot=/src/django_bpp/staticroot

if [ ! -L $staticroot ]; then
    mkdir -p /staticroot
    cp -R $staticroot/* /staticroot
    rm -rf $staticroot
    ln -s /staticroot $staticroot
fi
echo "done."

echo -n "Database migrations, if any... "
./src/manage.py migrate
echo "done."

echo "Starting uvicorn..."
uvicorn --host 0 --port 8000 django_bpp.asgi:application
