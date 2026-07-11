"""Testy autocomplete autorów dla importu pracowników (``ImportAutorAutocomplete``).

Kontrakt (plan T1.1):
- zakres = autorzy KIEDYKOLWIEK związani z uczelnią (obecnie LUB historycznie),
- autorzy zupełnie niezwiązani z uczelnią NIE pojawiają się,
- picker NIE oferuje opcji „Utwórz «…»" (``create_field = None`) — inwariant
  dry-run importu.
"""

import json
from datetime import date

import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_import_autor_autocomplete_historyczny_jest_w_wynikach(admin_client, uczelnia):
    """Autor z HISTORYCZNYM Autor_Jednostka do jednostki uczelni (bez etatu
    aktualnego) jest w wynikach dla zapytania po nazwisku."""
    jednostka = baker.make("bpp.Jednostka", uczelnia=uczelnia)
    autor = baker.make("bpp.Autor", nazwisko="Zzhistoryczny", imiona="Jan")
    baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(1999, 1, 1),
        zakonczyl_prace=date(2000, 1, 1),
    )

    res = admin_client.get(
        reverse("bpp:import-autor-autocomplete"), data={"q": "Zzhistoryczny"}
    )
    assert res.status_code == 200

    data = json.loads(res.content)
    ids = [item["id"] for item in data["results"]]
    assert str(autor.pk) in ids


@pytest.mark.django_db
def test_import_autor_autocomplete_niezwiazany_nie_jest_w_wynikach(
    admin_client, uczelnia
):
    """Autor bez żadnego powiązania z uczelnią NIE jest w wynikach."""
    autor = baker.make("bpp.Autor", nazwisko="Zzzewnetrzny", imiona="Anna")

    res = admin_client.get(
        reverse("bpp:import-autor-autocomplete"), data={"q": "Zzzewnetrzny"}
    )
    assert res.status_code == 200

    data = json.loads(res.content)
    ids = [item["id"] for item in data["results"]]
    assert str(autor.pk) not in ids


@pytest.mark.django_db
def test_import_autor_autocomplete_brak_opcji_create(admin_client, uczelnia):
    """Odpowiedź JSON nie zawiera opcji „create" (klucz ``create_id``)."""
    res = admin_client.get(
        reverse("bpp:import-autor-autocomplete"), data={"q": "Cokolwiek"}
    )
    assert res.status_code == 200

    data = json.loads(res.content)
    assert all("create_id" not in item for item in data["results"])
