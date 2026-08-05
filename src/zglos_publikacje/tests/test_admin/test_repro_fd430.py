"""Freshdesk #430 — przycisk „Użyj importera" nad tabelą, nie w wierszu.

Oczekiwane zachowanie na stronie edycji zgłoszenia publikacji w adminie:

* przycisk „Użyj importera" ma być w pasku akcji NAD tabelą (blok
  ``object-tools``), a nie renderowany jako readonly wiersz tabeli;
* gdy z adresu da się wyłuskać DOI → importer z providerem CrossRef;
* gdy adres nie jest DOI-em, ale jest — importer z providerem „Pozostałe
  strony WWW" (import z ogólnej strony), a nie CrossRef;
* gdy zgłoszenie nie ma żadnego adresu — przycisku nie ma w ogóle.
"""

import re

import pytest
from django.urls import reverse
from model_bakery import baker

from zglos_publikacje.models import Zgloszenie_Publikacji


def _change_html(admin_client, zgloszenie):
    change_url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_change",
        args=[zgloszenie.pk],
    )
    response = admin_client.get(change_url)
    assert response.status_code == 200
    return response.content.decode()


def _object_tools_fragment(html):
    """Wytnij zawartość paska akcji ``<ul class="…object-tools">…</ul>``.

    Grappelli renderuje pasek jako ``grp-object-tools`` — dopuszczamy oba.
    """
    match = re.search(
        r'<ul class="[^"]*object-tools">(.*?)</ul>', html, flags=re.DOTALL
    )
    assert match, "Brak paska object-tools na stronie edycji"
    return match.group(1)


@pytest.mark.django_db
def test_repro_fd430_przycisk_nad_tabela_z_doi(admin_client):
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca z DOI",
        strona_www="https://doi.org/10.1234/abc.def",
    )

    html = _change_html(admin_client, zgloszenie)

    # Przycisk jest w pasku akcji nad tabelą…
    tools = _object_tools_fragment(html)
    assert "Użyj importera" in tools
    assert "provider=CrossRef" in tools
    assert "10.1234%2Fabc.def" in tools

    # …i wyłącznie tam — nie jako readonly wiersz w tabeli formularza.
    assert "Użyj importera" not in html.replace(tools, "")


@pytest.mark.django_db
def test_repro_fd430_www_provider_gdy_adres_nie_jest_doi(admin_client):
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca bez DOI, ze stroną WWW",
        strona_www="https://example.com/papers/123",
    )

    tools = _object_tools_fragment(_change_html(admin_client, zgloszenie))

    assert "Użyj importera" in tools
    # Nie CrossRef, tylko import z ogólnej strony WWW.
    assert "provider=CrossRef" not in tools
    assert "provider=Pozosta%C5%82e+strony+WWW" in tools
    assert "identifier=https%3A%2F%2Fexample.com%2Fpapers%2F123" in tools


@pytest.mark.django_db
def test_repro_fd430_brak_przycisku_bez_adresu(admin_client):
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca bez adresu",
        strona_www="",
    )

    html = _change_html(admin_client, zgloszenie)

    assert "Użyj importera" not in html
