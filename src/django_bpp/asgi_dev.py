"""Development ASGI application with Django static-file serving enabled."""

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

from django_bpp.asgi import application as asgi_application

application = ASGIStaticFilesHandler(asgi_application)
