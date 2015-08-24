# -*- encoding: utf-8 -*-

from django_bpp.celery import app


@app.task
def eksport_pbn():
    pass