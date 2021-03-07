# -*- encoding: utf-8 -*-

from celery.utils.log import get_task_logger
from django.core.management import call_command

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from requests.exceptions import ConnectionError

from bpp.util import remove_old_objects
from integrator2.models.lista_ministerialna import ListaMinisterialnaIntegration
from long_running.util import wait_for_object

logger = get_task_logger(__name__)
from django_bpp.celery_tasks import app


@app.task
def analyze_file(pk):
    obj = wait_for_object(ListaMinisterialnaIntegration, pk)

    def informuj(komunikat, dont_persist=True):
        try:
            msg = '<a href="%s">Integracja pliku "%s": %s</a>. '
            url = reverse(
                "integrator2:detail",
                args=(
                    obj._meta.model_name,
                    obj.pk,
                ),
            )
            call_command(
                "send_message",
                obj.owner,
                msg % (url, obj.filename(), komunikat),
                dont_persist=dont_persist,
            )
        except ConnectionError:
            pass
        except Exception as e:
            obj.extra_info = str(e)
            obj.status = 3
            obj.save()
            raise

    obj.status = 1
    obj.save()

    try:
        obj.dict_stream_to_db()
    except Exception as e:
        obj.extra_info = str(e)
        obj.status = 3
        obj.save()

        informuj("wystąpił błąd na etapie importu danych")
        raise

    informuj("zaimportowano, trwa analiza danych")

    try:
        obj.match_records()
    except Exception as e:
        obj.extra_info = str(e)
        obj.status = 3
        obj.save()

        informuj("wystąpił błąd na etapie matchowania danych")
        raise

    informuj("rozpoczęto integrację")

    try:
        obj.integrate()
    except Exception as e:
        obj.extra_info = str(e)
        obj.status = 3
        obj.save()
        informuj("wystąpił błąd na etapie integracji danych")
        raise

    obj.status = 2
    obj.save()

    informuj("zakończono integrację", dont_persist=False)


@app.task
def remove_old_integrator_files():
    return remove_old_objects(ListaMinisterialnaIntegration, field_name="uploaded_on")
