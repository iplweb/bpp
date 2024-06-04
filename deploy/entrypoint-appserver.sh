#!/bin/sh

staticroot=/src/django_bpp/staticroot

if [ ! -L $staticroot ]; then
    mkdir -p /staticroot
    cp -R $staticroot/* /staticroot
    rm -rf $staticroot
    ln -s /staticroot $staticroot
fi

exec uvicorn --host 0 --port 8000 django_bpp.asgi:application
