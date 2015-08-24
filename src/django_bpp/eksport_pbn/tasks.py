# -*- encoding: utf-8 -*-
from bpp.models.struktura import Wydzial

from django_bpp.celery import app


@app.task
def eksport_pbn(wydzial_id, rok):
    wydzial = Wydzial.objects.get(pk=wydzial_id)

    