"""Strażnik wydajności listy wyników importu: brak N+1.

Widok renderował 3 zapytania NA WIERSZ importu (przy 1000 wierszy: 3035 zapytań,
3,15 s, 9,1 MB HTML):

- 2× ``bpp_uczelnia`` — ``Jednostka.__str__`` czyta ``uczelnia.uzywaj_wydzialow``,
  a szablon renderuje dwie jednostki na wiersz (``select_related`` daje osobną
  instancję ``Jednostka`` per wiersz, więc cache FK na instancji nie pomaga);
- 1× ``bpp_autor_jednostka`` — memo ``_aj_lista_cache`` jest per-wiersz.

Test nie sprawdza konkretnej liczby zapytań (ta zmienia się przy każdej
niepowiązanej zmianie w ``base.html`` czy middleware), tylko **niezależność od
N** — czyli dokładnie własność, którą łamie każde N+1. Rośnie liczba wierszy,
liczba zapytań stoi w miejscu.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_TWARDY


def _import_z_wierszami(admin_user, ile):
    """Import w stanie edytowalnym, z ``ile`` wierszami dopasowanymi twardo.

    Każdy wiersz ma autora z INNĄ aktualną jednostką niż docelowa — dzięki temu
    szablon renderuje obie jednostki (ścieżka ``__str__`` → ``uczelnia``)
    i uruchamia kolumnę przepięcia prac.
    """
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    stara = baker.make(Jednostka)
    nowa = baker.make(Jednostka)
    for i in range(ile):
        autor = baker.make(Autor, nazwisko=f"Nazwisko{i}", imiona="Jan")
        autor.aktualna_jednostka = stara
        autor.save()
        Autor_Jednostka.objects.create(autor=autor, jednostka=stara)
        ImportPracownikowRow.objects.create(
            parent=imp,
            autor=autor,
            jednostka=nowa,
            confidence=STATUS_TWARDY,
            zmiany_potrzebne=False,
            dane_znormalizowane={
                "imię": "Jan",
                "nazwisko": f"Nazwisko{i}",
                "email": f"jan{i}@example.com",
                "data_zatrudnienia": "2020-01-01",
                "tytuł_stopień": "dr",
            },
            dane_z_xls={"__xls_loc_sheet__": 0, "__xls_loc_row__": i},
        )
    return imp


def _ile_zapytan(client, imp):
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    client.get(url)  # rozgrzewka: cache szablonów, sesja, uprawnienia
    with CaptureQueriesContext(connection) as ctx:
        odpowiedz = client.get(url)
    assert odpowiedz.status_code == 200
    return len(ctx.captured_queries)


@pytest.mark.django_db
def test_liczba_zapytan_nie_rosnie_z_liczba_wierszy(admin_client, admin_user):
    """Pięciokrotnie więcej wierszy → tyle samo zapytań."""
    maly = _import_z_wierszami(admin_user, 5)
    duzy = _import_z_wierszami(admin_user, 25)

    zapytan_maly = _ile_zapytan(admin_client, maly)
    zapytan_duzy = _ile_zapytan(admin_client, duzy)

    assert zapytan_duzy == zapytan_maly, (
        f"N+1 w widoku wyników importu: 5 wierszy → {zapytan_maly} zapytań, "
        f"25 wierszy → {zapytan_duzy}. Liczba zapytań MUSI być stała względem "
        f"liczby wierszy (różnica {zapytan_duzy - zapytan_maly} = "
        f"{(zapytan_duzy - zapytan_maly) / 20:.2f} zapytania na wiersz)."
    )


@pytest.mark.django_db
def test_blok_select2_renderowany_raz_na_strone(admin_client, admin_user):
    """Skrypt inicjalizujący Select2 jest w HTML-u RAZ, nie raz na wiersz.

    Blok ma ~3,8 KB; powielony per wiersz dawał megabajty duplikatu w odpowiedzi.
    """
    imp = _import_z_wierszami(admin_user, 10)
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})

    tresc = admin_client.get(url).content.decode("utf-8")

    assert tresc.count("__bppImportAutorPicker") == 2, (
        "Blok Select2 ma wystąpić raz na stronę (guard czytany i ustawiany = "
        "2 wystąpienia identyfikatora), a nie raz na wiersz importu."
    )
