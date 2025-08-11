import contextlib
from importlib import import_module

import pytest
from celery.result import AsyncResult
from django.urls import reverse
from model_bakery import baker

from rozbieznosci_dyscyplin.admin import (
    DYSCYPLINA_AUTORA,
    OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
    SUBDYSCYPLINA_AUTORA,
    RozbieznosciViewAdmin,
    parse_object_id,
    ustaw_druga_dyscypline,
    ustaw_dyscypline_task_or_instant,
    ustaw_pierwsza_dyscypline,
)
from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView

from django.contrib.admin import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware

from bpp.models import Autor_Dyscyplina, Dyscyplina_Zrodla, Wydawnictwo_Ciagle


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
        "UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = %s WHERE id = %s"
        % (dyscyplina3.pk, wca.pk)
    )

    # wca.dyscyplina_naukowa_id = dyscyplina3
    #     dyscyplina_naukowa=dyscyplina3)

    return wydawnictwo_ciagle


@pytest.mark.django_db
def test_znajdz_rozbieznosci_gdy_przypisanie_autor_dyscyplina(
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

    wca = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    assert RozbieznosciView.objects.count() == 0

    wca.dyscyplina_naukowa = dyscyplina2
    wca.save()

    assert RozbieznosciView.objects.count() == 0

    from django.db import connection

    cur = connection.cursor()
    cur.execute(
        "UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = %s WHERE id = %s"
        % (dyscyplina3.pk, wca.pk)
    )

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski


@pytest.mark.django_db
def test_znajdz_rozbieznosci_bez_przypisania_autor_dyscyplina(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    wydawnictwo_ciagle,
    rok,
):
    wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    from django.db import connection

    cursor = connection.cursor()
    cursor.execute(
        "UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = %s WHERE id = %s"
        % (dyscyplina1.pk, wca.pk)
    )

    assert RozbieznosciView.objects.count() == 1

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_redirect_to_admin_view(wydawnictwo_ciagle, client, admin_user):
    res = client.get(
        reverse(
            "rozbieznosci_dyscyplin:redirect-to-admin",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(
                    wydawnictwo_ciagle
                ).pk,
                "object_id": wydawnictwo_ciagle.pk,
            },
        )
    )
    assert res.status_code == 302

    client.login(username=admin_user.username, password="password")
    res2 = client.get(res.url)

    assert res2.status_code == 200


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_pierwsza(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_pierwsza_dyscypline(None, req, None)
        msg = get_messages(req)

    assert RozbieznosciView.objects.count() == 0
    assert "ustawiono dyscyplinę" in list(msg)[0].message


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_druga(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_druga_dyscypline(None, req, None)
        assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_pusta_druga(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1

    ad = Autor_Dyscyplina.objects.get(
        autor=zle_przypisana_praca.autorzy.first(), rok=zle_przypisana_praca.rok
    )
    ad.subdyscyplina_naukowa = None
    ad.save()

    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_druga_dyscypline(None, req, None)
        msg = get_messages(req)

    assert "jest żadna" in list(msg)[0].message
    assert RozbieznosciView.objects.count() == 1


def test_RozbieznosciDyscyplinAdmin_przypisz_pierwsza_wszystkim(
    zle_przypisana_praca, rf, dyscyplina1
):
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")
    with middleware(req):
        ra.przypisz_wszystkim(req)
    assert RozbieznosciView.objects.count() == 0
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_przypisz_druga_wszystkim(
    zle_przypisana_praca, rf, dyscyplina2
):
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")
    with middleware(req):
        ra.przypisz_druga_wszystkim(req)
    assert RozbieznosciView.objects.count() == 0
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_offloads_dyscyplina(
    rf, zle_przypisana_praca, dyscyplina1
):
    req = rf.get("/")
    lst = [
        RozbieznosciView.objects.first().pk
    ] * OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(DYSCYPLINA_AUTORA, req, lst)
    assert isinstance(ret, AsyncResult)
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_offloads_subdyscyplina(
    rf, zle_przypisana_praca, dyscyplina2
):
    req = rf.get("/")
    lst = [
        RozbieznosciView.objects.first().pk
    ] * OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(SUBDYSCYPLINA_AUTORA, req, lst)
    assert isinstance(ret, AsyncResult)
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_instant_dyscyplina(
    rf, zle_przypisana_praca, dyscyplina1
):
    req = rf.get("/")
    lst = [RozbieznosciView.objects.first().pk] * (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE - 1
    )
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(DYSCYPLINA_AUTORA, req, lst)
    assert ret is None

    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_instant_subdyscyplina(
    rf, zle_przypisana_praca, dyscyplina2
):
    req = rf.get("/")
    lst = [RozbieznosciView.objects.first().pk] * (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE - 1
    )
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(SUBDYSCYPLINA_AUTORA, req, lst)
    assert ret is None

    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


@pytest.mark.parametrize(
    "i,o",
    [
        ("(1,1,1)", [1, 1, 1]),
        ("asdf", None),
        ("(389489,34893489,4893398489)", [389489, 34893489, 4893398489]),
        ("(1,2,3,4)", None),
        ("[1,2,3]", [1, 2, 3]),
        ("{1:1,2:2,3:3}", None),
    ],
)
def test_parse_object_id(i, o):
    assert parse_object_id(i) == o


def test_RozbieznosciAutorZrodloAdmin(admin_app):
    res = admin_app.get(
        reverse("admin:rozbieznosci_dyscyplin_rozbieznoscizrodelview_changelist")
    )
    assert res.status_code == 200


def test_RozbieznosciZrodelView(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
):
    assert RozbieznosciZrodelView.objects.count() == 0

    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc: Wydawnictwo_Ciagle = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    wc.dodaj_autora(
        autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1
    )  # Zrodlo nie ma tej dysc.

    assert RozbieznosciZrodelView.objects.count() == 1

    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina1)
    assert RozbieznosciZrodelView.objects.count() == 0
