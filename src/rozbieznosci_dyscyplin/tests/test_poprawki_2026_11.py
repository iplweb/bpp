"""Rows without an author discipline, export columns, task status page."""

import time
import uuid
from unittest import mock

import pytest
from django.urls import reverse

from bpp.models import Autor_Dyscyplina
from rozbieznosci_dyscyplin.admin import (
    SESSION_KEY_ZADANIA,
    RozbieznosciViewResource,
)
from rozbieznosci_dyscyplin.models import RozbieznosciView


@pytest.fixture
def praca_autora_bez_dyscypliny(zle_przypisana_praca):
    """The author loses the discipline for the year; the work keeps one."""
    Autor_Dyscyplina.objects.filter(
        autor=zle_przypisana_praca.autorzy.first(), rok=zle_przypisana_praca.rok
    ).delete()
    from django.db import connection

    with connection.cursor() as c:
        # The trigger clears the work's discipline on delete; put one back.
        c.execute(
            "UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = "
            "(SELECT id FROM bpp_dyscyplina_naukowa LIMIT 1) "
            "WHERE rekord_id = %s",
            [zle_przypisana_praca.pk],
        )
    return zle_przypisana_praca


@pytest.mark.django_db
def test_wiersz_bez_dyscypliny_autora_widoczny_w_tabeli(
    praca_autora_bez_dyscypliny, admin_app
):
    assert RozbieznosciView.objects.filter(dyscyplina_autora=None).count() == 1

    res = admin_app.get(
        reverse("admin:rozbieznosci_dyscyplin_rozbieznosciview_changelist")
    )
    # Counter and table must agree: one row in the result list.
    assert len(res.html.select("#result_list tbody tr")) == 1


@pytest.mark.django_db
def test_eksport_ma_dyscypline_rekordu_i_rok(zle_przypisana_praca, dyscyplina3, rf):
    req = rf.get("/")
    dataset = RozbieznosciViewResource(request=req).export(
        RozbieznosciView.objects.all()
    )
    assert "nazwa_dyscypliny_rekordu" in dataset.headers
    assert "rok" in dataset.headers
    row = dict(zip(dataset.headers, dataset[0], strict=True))
    assert row["nazwa_dyscypliny_rekordu"] == dyscyplina3.nazwa


def _status(client, mocker, *, state, result=None, start=None, powrot=None):
    task_id = str(uuid.uuid4())
    session = client.session
    session[SESSION_KEY_ZADANIA] = [
        {
            "id": task_id,
            "start": time.time() if start is None else start,
            "powrot": powrot
            or "/admin/rozbieznosci_dyscyplin/rozbieznosciview/?rok=2023",
        }
    ]
    session.save()

    wynik = mocker.MagicMock()
    wynik.state = state
    wynik.ready.return_value = state in ("SUCCESS", "FAILURE", "REVOKED")
    wynik.successful.return_value = state == "SUCCESS"
    wynik.failed.return_value = state == "FAILURE"
    wynik.result = result
    mocker.patch("rozbieznosci_dyscyplin.views.AsyncResult", return_value=wynik)
    return client.get(reverse("rozbieznosci_dyscyplin:status-zadania", args=[task_id]))


@pytest.mark.django_db
def test_status_zadania_obcego_404(admin_client):
    url = reverse("rozbieznosci_dyscyplin:status-zadania", args=[str(uuid.uuid4())])
    assert admin_client.get(url).status_code == 404


@pytest.mark.django_db
def test_status_zadania_rozdziela_pominiete_i_zmienione(admin_client, mocker):
    res = _status(
        admin_client,
        mocker,
        state="SUCCESS",
        result=[
            ["info", "Dla rekordu <b>X</b> ustawiono dyscyplinę."],
            ["warning", "Dla rekordu Y nie ustawiono dyscypliny."],
        ],
    )
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "Ustawiono dyscyplinę: <strong>1</strong>" in tresc
    assert "pominięto: <strong>1</strong>" in tresc
    assert '<li class="warning">Dla rekordu Y' in tresc
    assert "<b>X</b>" in tresc
    assert 'http-equiv="refresh"' not in tresc
    # "Back to the list" keeps the editor's filters.
    assert "rozbieznosciview/?rok=2023" in tresc


@pytest.mark.django_db
def test_status_zadania_w_toku_odswieza(admin_client, mocker):
    res = _status(admin_client, mocker, state="STARTED")
    tresc = res.content.decode()
    assert "w toku" in tresc
    assert 'http-equiv="refresh"' in tresc


@pytest.mark.django_db
def test_status_zadania_zagubione_nie_odswieza(admin_client, mocker):
    res = _status(admin_client, mocker, state="PENDING", start=time.time() - 2 * 3600)
    tresc = res.content.decode()
    assert "Wynik tego zadania jest niedostępny" in tresc
    assert 'http-equiv="refresh"' not in tresc


@pytest.mark.django_db
def test_status_zadania_blad(admin_client, mocker):
    res = _status(admin_client, mocker, state="FAILURE", result=RuntimeError("x"))
    assert "Przetwarzanie przerwał błąd" in res.content.decode()


@pytest.mark.django_db
def test_status_zadania_anulowane(admin_client, mocker):
    tresc = _status(admin_client, mocker, state="REVOKED").content.decode()
    assert "anulowane" in tresc
    assert "Ustawiono dyscyplinę" not in tresc
    assert "Zadanie nie zostało wykonane" in tresc


@pytest.mark.django_db
def test_status_zadania_obcy_powrot_zastapiony(admin_client, mocker):
    res = _status(
        admin_client, mocker, state="SUCCESS", result=[], powrot="https://evil.example/"
    )
    assert "evil.example" not in res.content.decode()


@pytest.mark.django_db
def test_status_zadania_bez_uprawnien_403(client, django_user_model, mocker):
    user = django_user_model.objects.create_user("bez", password="bez")
    client.force_login(user)
    res = _status(client, mocker, state="SUCCESS", result=[])
    assert res.status_code == 403


@pytest.mark.django_db
def test_status_zadania_wymaga_logowania(client):
    url = reverse("rozbieznosci_dyscyplin:status-zadania", args=[str(uuid.uuid4())])
    assert client.get(url).status_code == 302


@pytest.mark.django_db
def test_zadanie_w_tle_escapuje_dane(zle_przypisana_praca):
    """Background messages are rendered with |safe, so data must be escaped."""
    from rozbieznosci_dyscyplin.admin import (
        DYSCYPLINA_AUTORA,
        ResultNotifier,
        real_ustaw_dyscypline,
    )

    autor = zle_przypisana_praca.autorzy.first()
    autor.nazwisko = "<script>alert(1)</script>"
    autor.save()

    notifier = ResultNotifier()
    real_ustaw_dyscypline(
        DYSCYPLINA_AUTORA, [RozbieznosciView.objects.first().pk], notifier
    )
    assert notifier.retbuf
    for _poziom, tresc in notifier.retbuf:
        assert "<script>" not in tresc


@pytest.mark.django_db
def test_autor_usuniety_z_pracy_pominiety(zle_przypisana_praca):
    from rozbieznosci_dyscyplin.admin import (
        DYSCYPLINA_AUTORA,
        ResultNotifier,
        real_ustaw_dyscypline,
    )

    pk = RozbieznosciView.objects.first().pk
    notifier = ResultNotifier()
    with mock.patch.object(
        RozbieznosciView, "get_wydawnictwo_autor_obj", return_value=None
    ):
        real_ustaw_dyscypline(DYSCYPLINA_AUTORA, [pk], notifier)
    assert notifier.retbuf[0][0] == "warning"
    assert "nie ma już autora" in notifier.retbuf[0][1]


@pytest.mark.django_db
def test_akcja_pomija_wiersze_spoza_zakresu_admina(zle_przypisana_praca, rf):
    """Selected IDs outside ModelAdmin.get_queryset() (other university) are ignored."""
    from rozbieznosci_dyscyplin.admin import DYSCYPLINA_AUTORA, ustaw_dyscypline

    from .conftest import middleware

    pk = RozbieznosciView.objects.first().pk
    admin = mock.MagicMock()
    admin.get_queryset.return_value = RozbieznosciView.objects.none()
    req = rf.post("/", data={"_selected_action": [str(pk)]})
    with middleware(req):
        ustaw_dyscypline(DYSCYPLINA_AUTORA, admin, req, None)
    assert RozbieznosciView.objects.count() == 1


def test_zadanie_sledzi_start():
    from rozbieznosci_dyscyplin.tasks import task_ustaw_dyscypline

    assert task_ustaw_dyscypline.track_started is True


def test_naglowki_zrodel_po_polsku():
    from rozbieznosci_dyscyplin.models import RozbieznosciZrodelView

    f = RozbieznosciZrodelView._meta.get_field
    assert f("zrodlo").verbose_name == "źródło"
    assert f("wydawnictwo_ciagle").verbose_name == "wydawnictwo ciągłe"
    assert f("punkty_kbn").verbose_name == "punkty MNiSW"
