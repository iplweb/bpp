"""Paginacja serwerowa i filtry w SQL na liście wyników importu.

Istotą zmiany jest to, że filtr obejmuje CAŁY import, a nie to, co akurat jest
w DOM-ie. Dawny filtr kliencki po wprowadzeniu paginacji widziałby wyłącznie
bieżącą stronę — deep-link „pokaż wiersze do pominięcia" z ostrzeżenia
finalizacji trafiałby wtedy w pustkę. Dlatego testy filtrów celowo umieszczają
szukany wiersz POZA pierwszą stroną.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY
from import_pracownikow.views import DOMYSLNY_ROZMIAR_STRONY


def _url(imp):
    return reverse(
        "import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk}
    )


def _import(admin_user, **kw):
    kw.setdefault("stan", ImportPracownikow.STAN_PRZEANALIZOWANY)
    return baker.make(
        ImportPracownikow, owner=admin_user, finished_successfully=True, **kw
    )


def _wiersz(imp, nr, **kw):
    kw.setdefault("confidence", STATUS_TWARDY)
    kw.setdefault("zmiany_potrzebne", False)
    kw.setdefault("dane_znormalizowane", {"imię": "Jan", "nazwisko": f"Nazwisko{nr}"})
    kw.setdefault("dane_z_xls", {"__xls_loc_sheet__": 0, "__xls_loc_row__": nr})
    row = ImportPracownikowRow.objects.create(parent=imp, **kw)
    row.stany_pol_snapshot = row.stany_pol_live()
    row.save(update_fields=["stany_pol_snapshot"])
    return row


@pytest.mark.django_db
def test_strona_zawiera_najwyzej_paginate_by_wierszy(admin_client, admin_user):
    imp = _import(admin_user)
    for i in range(DOMYSLNY_ROZMIAR_STRONY + 7):
        _wiersz(imp, i)

    odpowiedz = admin_client.get(_url(imp))

    assert odpowiedz.context["paginator"].count == DOMYSLNY_ROZMIAR_STRONY + 7
    assert len(odpowiedz.context["object_list"]) == DOMYSLNY_ROZMIAR_STRONY
    assert odpowiedz.context["paginator"].num_pages == 2


@pytest.mark.django_db
def test_filtr_rodzaju_siega_poza_pierwsza_strone(admin_client, admin_user):
    """Wiersz „do pominięcia" na drugiej stronie MUSI zostać znaleziony.

    To jest deep-link z ostrzeżenia finalizacji (`?rodzaj=do-pominiecia`).
    Filtr kliencki znalazłby tylko to, co jest na bieżącej stronie.
    """
    imp = _import(admin_user)
    for i in range(DOMYSLNY_ROZMIAR_STRONY):
        _wiersz(imp, i, autor=baker.make(Autor))
    # Ostatni wiersz w kolejności pliku → ląduje na stronie 2.
    igla = _wiersz(
        imp,
        DOMYSLNY_ROZMIAR_STRONY + 1,
        autor=None,
        utworz_nowego=False,
        confidence=STATUS_BRAK,
    )

    odpowiedz = admin_client.get(_url(imp), {"rodzaj": "do-pominiecia"})

    znalezione = [r.pk for r in odpowiedz.context["object_list"]]
    assert znalezione == [igla.pk]
    assert odpowiedz.context["paginator"].count == 1


@pytest.mark.django_db
def test_filtr_stanu_pola_siega_poza_pierwsza_strone(admin_client, admin_user):
    imp = _import(admin_user)
    zgodna = baker.make(Jednostka)
    for i in range(DOMYSLNY_ROZMIAR_STRONY):
        autor = baker.make(Autor)
        autor.aktualna_jednostka = zgodna
        autor.save()
        _wiersz(imp, i, autor=autor, jednostka=zgodna)  # stan „zgodne"
    autor = baker.make(Autor)
    autor.aktualna_jednostka = baker.make(Jednostka)
    autor.save()
    igla = _wiersz(
        imp, DOMYSLNY_ROZMIAR_STRONY + 1, autor=autor, jednostka=zgodna
    )  # stan „zmienione"

    odpowiedz = admin_client.get(_url(imp), {"stan_jednostka": "zmienione"})

    assert [r.pk for r in odpowiedz.context["object_list"]] == [igla.pk]


@pytest.mark.django_db
def test_filtr_stanu_brak_znajduje_snapshoty_bez_klucza(admin_client, admin_user):
    """Zamrożone snapshoty sprzed dodania `data_od`/`data_do` nie mają tych
    kluczy — równość w SQL by ich nie znalazła, mimo że ``stany_pol()``
    dopełnia je w Pythonie wartością „brak"."""
    imp = _import(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    stary = _wiersz(imp, 1)
    stary.stany_pol_snapshot = {"jednostka": "zgodne"}  # BEZ klucza data_od
    stary.save(update_fields=["stany_pol_snapshot"])

    odpowiedz = admin_client.get(_url(imp), {"stan_data_od": "brak"})

    assert [r.pk for r in odpowiedz.context["object_list"]] == [stary.pk]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fraza,pole",
    [
        ("Wyjatkowe", "autor__imiona"),
        ("Osobliwa", "autor__aktualna_jednostka__nazwa"),
        ("0000-0002-1825-0097", "autor__orcid"),
    ],
)
def test_szukanie_obejmuje_pola_z_kolumny_autora(admin_client, admin_user, fraza, pole):
    """``?q=`` pokrywa to, co renderuje kolumna „Autor (BPP)".

    Kliencki filtr przeszukiwał cały wyrenderowany blok `_autor_dane.html`
    (imiona, ORCID) oraz nazwę aktualnej jednostki. Naiwna wersja serwerowa
    ograniczona do nazwiska byłaby cichym zawężeniem.
    """
    imp = _import(admin_user)
    autor = baker.make(Autor, nazwisko="Zwykly", imiona="Jan")
    autor.aktualna_jednostka = baker.make(Jednostka)
    autor.save()
    _wiersz(imp, 1, autor=autor)

    szukany = baker.make(Autor, nazwisko="Zwykly", imiona="Jan")
    if pole == "autor__imiona":
        szukany.imiona = fraza
    elif pole == "autor__orcid":
        szukany.orcid = fraza
    else:
        szukany.aktualna_jednostka = baker.make(Jednostka, nazwa=fraza)
    szukany.save()
    igla = _wiersz(imp, 2, autor=szukany)

    odpowiedz = admin_client.get(_url(imp), {"q": fraza})

    assert [r.pk for r in odpowiedz.context["object_list"]] == [igla.pk]


@pytest.mark.django_db
def test_linki_pagera_zachowuja_filtry(admin_client, admin_user):
    """Przejście na kolejną stronę nie gubi aktywnych filtrów."""
    imp = _import(admin_user)
    for i in range(DOMYSLNY_ROZMIAR_STRONY + 5):
        _wiersz(imp, i, confidence=STATUS_TWARDY)

    tresc = admin_client.get(
        _url(imp), {"rodzaj": STATUS_TWARDY, "q": ""}
    ).content.decode()

    assert "page=2" in tresc
    assert f"rodzaj={STATUS_TWARDY}" in tresc, (
        "link pagera zgubił filtr — druga strona pokazałaby niefiltrowany zbiór"
    )
