"""Wspólne fixtures i helpery testów `rozbieznosci_dyscyplin`."""

import contextlib
from importlib import import_module

import pytest
from django.contrib.messages.middleware import MessageMiddleware

from bpp.models import Autor_Dyscyplina


@contextlib.contextmanager
def middleware(request):
    """Annotate a request object with a session"""

    from django.conf import settings

    engine = import_module(settings.SESSION_ENGINE)
    SessionStore = engine.SessionStore

    session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
    request.session = SessionStore(session_key)

    # middleware = SessionMiddleware()
    # middleware.process_request(request)
    request.session.save()

    """Annotate a request object with a messages"""
    middleware = MessageMiddleware([])
    middleware.process_request(request)
    request.session.save()
    yield request


@pytest.fixture
def zle_przypisana_praca(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    wydawnictwo_ciagle,
    rok,
):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    from django.db import connection

    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = {dyscyplina3.pk} WHERE id = {wca.pk}"
    )

    # wca.dyscyplina_naukowa_id = dyscyplina3
    #     dyscyplina_naukowa=dyscyplina3)

    return wydawnictwo_ciagle
