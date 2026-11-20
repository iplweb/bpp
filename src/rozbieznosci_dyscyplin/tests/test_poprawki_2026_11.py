"""Rows without an author discipline, export columns, task status page."""

import uuid

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


@pytest.mark.django_db
def test_status_zadania_obcego_404(admin_client):
    url = reverse("rozbieznosci_dyscyplin:status-zadania", args=[str(uuid.uuid4())])
    assert admin_client.get(url).status_code == 404


@pytest.mark.django_db
def test_status_zadania_wlasnego(admin_client, mocker):
    task_id = str(uuid.uuid4())
    session = admin_client.session
    session[SESSION_KEY_ZADANIA] = [task_id]
    session.save()

    wynik = mocker.MagicMock()
    wynik.state = "SUCCESS"
    wynik.ready.return_value = True
    wynik.successful.return_value = True
    wynik.failed.return_value = False
    wynik.result = ["Dla rekordu <b>X</b> ustawiono dyscyplinę."]
    mocker.patch("rozbieznosci_dyscyplin.views.AsyncResult", return_value=wynik)

    res = admin_client.get(
        reverse("rozbieznosci_dyscyplin:status-zadania", args=[task_id])
    )
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "zakończone" in tresc
    assert "<b>X</b>" in tresc


@pytest.mark.django_db
def test_status_zadania_wymaga_logowania(client):
    url = reverse("rozbieznosci_dyscyplin:status-zadania", args=[str(uuid.uuid4())])
    assert client.get(url).status_code == 302


def test_naglowki_zrodel_po_polsku():
    from rozbieznosci_dyscyplin.models import RozbieznosciZrodelView

    f = RozbieznosciZrodelView._meta.get_field
    assert f("zrodlo").verbose_name == "źródło"
    assert f("wydawnictwo_ciagle").verbose_name == "wydawnictwo ciągłe"
    assert f("punkty_kbn").verbose_name == "punkty MNiSW"
