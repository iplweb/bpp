"""Publiczne autocomplete wydawnictwa nadrzędnego rozumie ISBN.

To samo zachowanie, co w adminie: ISBN znajduje rekord niezależnie od tego,
czy myślniki są po stronie wpisu, po stronie bazy, czy po żadnej.
"""

import json

import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_api.models.publication import Publication as PBN_Publication

ISBN13_Z_MYSLNIKAMI = "978-83-7430-700-0"
ISBN13_BEZ_MYSLNIKOW = "9788374307000"


def _etykiety(res):
    """Etykiety wyników. Select2QuerySetSequenceView grupuje je po modelu,
    więc właściwe pozycje siedzą w ``children``."""
    etykiety = []
    for grupa in json.loads(res.content)["results"]:
        etykiety += [dziecko["text"] for dziecko in grupa.get("children", [])]
    return etykiety


@pytest.mark.django_db
def test_public_wn_autocomplete_znajduje_ksiazke_bpp_po_isbn(client, ksiazka):
    ksiazka.tytul_oryginalny = "Zupełnie inny tytuł"
    ksiazka.isbn = ISBN13_Z_MYSLNIKAMI
    ksiazka.save()

    res = client.get(
        reverse("zglos_publikacje:public-wydawnictwo-nadrzedne-autocomplete")
        + f"?q={ISBN13_BEZ_MYSLNIKOW}"
    )
    assert any("Zupełnie inny tytuł" in e for e in _etykiety(res))


@pytest.mark.django_db
def test_public_wn_autocomplete_znajduje_rekord_pbn_po_isbn(client):
    baker.make(
        PBN_Publication,
        mongoId="616e76ca2467f070ae3355dd",
        title="Interna Szczeklika 2021",
        isbn=ISBN13_BEZ_MYSLNIKOW,
    )

    res = client.get(
        reverse("zglos_publikacje:public-wydawnictwo-nadrzedne-autocomplete")
        + f"?q={ISBN13_Z_MYSLNIKAMI}"
    )
    assert any("Interna Szczeklika 2021" in e for e in _etykiety(res))
