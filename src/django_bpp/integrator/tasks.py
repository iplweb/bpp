# -*- encoding: utf-8 -*-

from celery.utils.log import get_task_logger
from django.core.management import call_command
from django.core.urlresolvers import reverse

from django_bpp.util import wait_for_object
from integrator.atoz import read_atoz_xls_data, atoz_import_data
from integrator.autorzy import autorzy_import_data, autorzy_analyze_data, autorzy_integrate_data, \
    real_autorzy_analyze_file
from integrator.doaj import doaj_import_data, read_doaj_csv_data, zrodlo_integrate_data, \
    zrodlo_analyze_data
from integrator.models import IntegrationFile, INTEGRATOR_AUTOR, \
    INTEGRATOR_ATOZ, INTEGRATOR_DOI

logger = get_task_logger(__name__)
from django_bpp.celery import app


@app.task
def analyze_file(pk):
    obj = wait_for_object(IntegrationFile, pk)

    def informuj(komunikat, dont_persist=True):
        try:
            msg = u'<a href="%s">Integracja pliku "%s": %s</a>. '
            url = reverse("integrator:detail", args=(obj.pk,))
            call_command('send_message', obj.owner, msg % (url, obj.filename(), komunikat), dont_persist=dont_persist)
        except Exception, e:
            obj.extra_info = str(e)
            obj.status = 3
            obj.save()
            raise

    obj.status = 1
    obj.save()

    if obj.type == INTEGRATOR_AUTOR:
        f1 = autorzy_import_data
        f1a = real_autorzy_analyze_file
        f2 = autorzy_analyze_data
        f3 = autorzy_integrate_data

    elif obj.type == INTEGRATOR_ATOZ:
        f1 = atoz_import_data
        f1a = read_atoz_xls_data
        f2 = zrodlo_analyze_data
        f3 = zrodlo_integrate_data

    elif obj.type == INTEGRATOR_DOI:
        f1 = doaj_import_data
        f1a = read_doaj_csv_data
        f2 = zrodlo_analyze_data
        f3 = zrodlo_integrate_data

    else:
        raise NotImplementedError

    try:
        f1(obj, f1a(obj.file))
    except Exception, e:
        obj.extra_info = str(e)
        obj.status = 3
        obj.save()

        informuj(u"wystąpił błąd")
        raise

    informuj(u"zaimportowano, trwa analiza danych")

    try:
        f2(obj)
    except Exception, e:
        obj.extra_info = str(e)
        obj.status = 3
        obj.save()

        informuj(u"wystąpił błąd")
        raise

    informuj(u"rozpoczęto integrację")

    f3(obj)
    obj.status = 2
    obj.save()

    informuj(u"zakończono integrację", dont_persist=False)
