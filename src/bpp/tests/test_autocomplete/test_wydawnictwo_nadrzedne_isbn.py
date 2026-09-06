"""Wyszukiwanie wydawnictwa nadrzędnego po ISBN.

ISBN-y w BPP zapisywane są tak, jak wpisał je użytkownik — część z myślnikami,
część bez. Wyszukiwanie musi znaleźć rekord niezależnie od tego, w której
formie jest zapisany i w której został wpisany.
"""

import json

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Zwarte

# ISBN-13 i jego odpowiednik ISBN-10 (poprawne sumy kontrolne).
ISBN13_Z_MYSLNIKAMI = "978-83-7430-700-0"
ISBN13_BEZ_MYSLNIKOW = "9788374307000"
ISBN10 = "8374307005"


def _tytuly(res):
    return [x["text"] for x in json.loads(res.content)["results"]]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "zapisany,wpisany",
    [
        (ISBN13_Z_MYSLNIKAMI, ISBN13_BEZ_MYSLNIKOW),
        (ISBN13_BEZ_MYSLNIKOW, ISBN13_Z_MYSLNIKAMI),
        (ISBN13_Z_MYSLNIKAMI, ISBN13_Z_MYSLNIKAMI),
        (ISBN13_BEZ_MYSLNIKOW, ISBN13_BEZ_MYSLNIKOW),
    ],
)
def test_wydawnictwo_nadrzedne_autocomplete_isbn_niezaleznie_od_myslnikow(
    admin_client, ksiazka, zapisany, wpisany
):
    ksiazka.tytul_oryginalny = "Zupełnie inny tytuł"
    ksiazka.isbn = zapisany
    ksiazka.save()

    res = admin_client.get(
        reverse("bpp:wydawnictwo-nadrzedne-autocomplete") + f"?q={wpisany}"
    )
    assert _tytuly(res) == ["Zupełnie inny tytuł"]


@pytest.mark.django_db
def test_wydawnictwo_nadrzedne_autocomplete_isbn10_znajduje_isbn13(
    admin_client, ksiazka
):
    """PBN ani baza nie przeliczają ISBN-10 na ISBN-13 — robi to wyszukiwarka."""
    ksiazka.tytul_oryginalny = "Zupełnie inny tytuł"
    ksiazka.isbn = ISBN13_Z_MYSLNIKAMI
    ksiazka.save()

    res = admin_client.get(
        reverse("bpp:wydawnictwo-nadrzedne-autocomplete") + f"?q={ISBN10}"
    )
    assert _tytuly(res) == ["Zupełnie inny tytuł"]


@pytest.mark.django_db
def test_wydawnictwo_nadrzedne_autocomplete_szuka_takze_po_e_isbn(
    admin_client, ksiazka
):
    ksiazka.tytul_oryginalny = "Zupełnie inny tytuł"
    ksiazka.isbn = ""
    ksiazka.e_isbn = ISBN13_Z_MYSLNIKAMI
    ksiazka.save()

    res = admin_client.get(
        reverse("bpp:wydawnictwo-nadrzedne-autocomplete") + f"?q={ISBN13_BEZ_MYSLNIKOW}"
    )
    assert _tytuly(res) == ["Zupełnie inny tytuł"]


@pytest.mark.django_db
def test_wydawnictwo_nadrzedne_autocomplete_nie_isbn_szuka_po_tytule(
    admin_client, ksiazka
):
    """Zwykły tekst ma dalej trafiać w wyszukiwanie po tytule."""
    ksiazka.tytul_oryginalny = "Interna Szczeklika 2021"
    ksiazka.isbn = ISBN13_Z_MYSLNIKAMI
    ksiazka.save()

    res = admin_client.get(
        reverse("bpp:wydawnictwo-nadrzedne-autocomplete") + "?q=Szczeklika"
    )
    assert _tytuly(res) == ["Interna Szczeklika 2021"]


@pytest.mark.django_db
def test_public_wydawnictwo_nadrzedne_autocomplete_isbn(admin_client, ksiazka):
    """Publiczny wariant też rozumie ISBN — zawężony do realnych nadrzędnych."""
    ksiazka.tytul_oryginalny = "Zupełnie inny tytuł"
    ksiazka.isbn = ISBN13_Z_MYSLNIKAMI
    ksiazka.save()
    baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=ksiazka)

    res = admin_client.get(
        reverse("bpp:public-wydawnictwo-nadrzedne-autocomplete")
        + f"?q={ISBN13_BEZ_MYSLNIKOW}"
    )
    assert _tytuly(res) == ["Zupełnie inny tytuł"]
