"""AuthorInfoView oddaje gotowy link do PBN (a nie sam identyfikator).

JavaScript w ``partials/step_authors.html`` sklejał adres z wpisanego na
sztywno ``https://pbn.nauka.gov.pl/core/#/person/view/``, więc w instalacji
multi-hosted link prowadził do cudzego (publicznego) PBN. Adres buduje teraz
backend, który zna uczelnię z requestu.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Uczelnia
from importer_publikacji.models import ImportSession


@pytest.fixture
def session(db):
    return baker.make(ImportSession)


@pytest.mark.django_db
def test_author_info_zwraca_link_do_pbn_uczelni(importer_client, settings):
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia = baker.make(Uczelnia, pbn_api_root="https://pbn-a.example.com")
    uczelnia.site.domain = "uczelnia-a.example.com"
    uczelnia.site.save()
    baker.make(Uczelnia)  # druga uczelnia → multi-hosted
    # Sesja importu jest zawężona do uczelni oglądającego (get_scoped_or_404).
    session = baker.make(ImportSession, uczelnia=uczelnia)

    from pbn_api.models import Scientist

    scientist = baker.make(Scientist)
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pbn_uid=scientist)

    url = reverse("importer_publikacji:author-info", args=[session.pk, autor.pk])
    response = importer_client.get(url, HTTP_HOST="uczelnia-a.example.com")

    assert response.status_code == 200
    data = response.json()
    assert data["pbn_url"] == (
        f"https://pbn-a.example.com/core/#/person/view/{scientist.pk}/current"
    )


@pytest.mark.django_db
def test_author_info_bez_pbn_uid_ma_pusty_link(session, importer_client):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pbn_uid=None)

    url = reverse("importer_publikacji:author-info", args=[session.pk, autor.pk])
    data = importer_client.get(url).json()

    assert data["pbn_url"] == ""


def test_szablon_nie_sklejza_adresu_pbn_w_javascripcie():
    """Strażnik: JS nie buduje adresu PBN z literału — bierze go z backendu."""
    from pathlib import Path

    szablon = (
        Path(__file__).resolve().parents[1]
        / "templates/importer_publikacji/partials/step_authors.html"
    )
    tekst = szablon.read_text(encoding="utf-8")

    assert "pbn.nauka.gov.pl" not in tekst
    assert "info.pbn_url" in tekst
