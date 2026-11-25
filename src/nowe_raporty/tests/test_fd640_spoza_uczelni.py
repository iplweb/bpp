"""FD#640 — raport autora (nowe_raporty) nie przyjmuje autora spoza uczelni."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka
from nowe_raporty.seeding import seed_default_reports

KOMUNIKAT = "jest autorem spoza uczelni"


@pytest.fixture
def autor_obcy(uczelnia_z_obca_jednostka, obca_jednostka):
    autor = baker.make(Autor, imiona="Ewa", nazwisko="Obca")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    return autor


@pytest.fixture
def autor_nasz(uczelnia_z_obca_jednostka, jednostka):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Nasz")
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    return autor


def _post(client, autor):
    seed_default_reports()  # raport-autorow -> WSZYSCY (anonim widzi)
    return client.post(
        reverse("nowe_raporty:raport_form", args=["raport-autorow"]),
        {
            "obiekt": autor.pk,
            "od_roku": 2022,
            "do_roku": 2022,
            "_export": "html",
            "sortowanie": "domyslne",
            "tylko_z_jednostek_uczelni": "on",
        },
    )


@pytest.mark.django_db
def test_fd640_formularz_raportu_autora_odrzuca_obcego(client, autor_obcy):
    res = _post(client, autor_obcy)
    assert res.status_code == 200
    assert KOMUNIKAT in res.content.decode("utf-8")


@pytest.mark.django_db
def test_fd640_formularz_raportu_autora_przyjmuje_naszego(client, autor_nasz):
    res = _post(client, autor_nasz)
    assert res.status_code == 302, res.content.decode("utf-8")[:2000]


@pytest.mark.django_db
def test_fd640_generuj_raport_autora_obcego_404(client, autor_obcy, autor_nasz):
    seed_default_reports()

    def url(autor):
        return reverse(
            "nowe_raporty:raport_generuj",
            args=["raport-autorow", autor.pk, 2022, 2022],
        )

    assert client.get(url(autor_obcy)).status_code == 404
    assert client.get(url(autor_nasz)).status_code == 200
