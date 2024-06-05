#!/bin/sh

createdb -h $DJANGO_BPP_DB_HOST -U $DJANGO_BPP_DB_USER $DJANGO_BPP_DB_NAME || true

staticroot=/src/django_bpp/staticroot

if [ ! -L $staticroot ]; then
    mkdir -p /staticroot
    cp -R $staticroot/* /staticroot
    rm -rf $staticroot
    ln -s /staticroot $staticroot
fi

./src/manage.py migrate

exec uvicorn --host 0 --port 8000 django_bpp.asgi:application
