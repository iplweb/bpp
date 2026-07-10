import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_null_autor_jednostka_nie_zeruje_zbioru(today):
    """Regresja §9: wiersz z ``autor_jednostka=None`` (odroczone AJ) NIE może
    wyzerować zbioru odpięć (stary ``NOT IN (…, NULL)`` dawał pusty zbiór).
    Para z pliku (autor, jednostka) jest chroniona, a AJ spoza pliku — nie."""
    j = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a_plik = baker.make(Autor, aktualna_jednostka=j)
    aj_plik = baker.make(Autor_Jednostka, autor=a_plik, jednostka=j)
    a_spoza = baker.make(Autor, aktualna_jednostka=j)
    aj_spoza = baker.make(Autor_Jednostka, autor=a_spoza, jednostka=j)

    imp = baker.make(ImportPracownikow)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=a_plik,
        jednostka=j,
        autor_jednostka=None,
        zmiany_potrzebne=False,
    )

    zbior = set(imp.autorzy_spoza_pliku_set(today=today))
    assert aj_spoza in zbior
    assert aj_plik not in zbior


@pytest.mark.django_db
def test_pomija_jednostki_nie_zarzadzane_automatycznie(today):
    j = baker.make(Jednostka, zarzadzaj_automatycznie=False)
    a = baker.make(Autor, aktualna_jednostka=j)
    baker.make(Autor_Jednostka, autor=a, jednostka=j)
    imp = baker.make(ImportPracownikow)
    assert list(imp.autorzy_spoza_pliku_set(today=today)) == []


@pytest.mark.django_db
def test_pomija_autorow_bez_aktualnej_jednostki(today):
    j = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a = baker.make(Autor, aktualna_jednostka=None)
    baker.make(Autor_Jednostka, autor=a, jednostka=j)
    # Trigger `bpp_autor_ustaw_jednostka_aktualna_trigger` (baseline.sql, AFTER
    # INSERT ON bpp_autor_jednostka) po wstawieniu aktywnego AJ NADPISUJE
    # autor.aktualna_jednostka_id = j — dlatego `baker.make(aktualna=None)` nie
    # przetrwa. Wymuszamy stan bezpośrednim UPDATE (NIE odpala triggera AJ), by
    # realnie sprawdzić kryterium `exclude(autor__aktualna_jednostka=None)`.
    Autor.objects.filter(pk=a.pk).update(aktualna_jednostka=None)
    imp = baker.make(ImportPracownikow)
    assert list(imp.autorzy_spoza_pliku_set(today=today)) == []


@pytest.mark.django_db
def test_pomija_juz_zakonczone(today, yesterday):
    """G3: izoluje kryterium ``zakonczyl_prace``. Autor dostaje DWA AJ:
    aktywne (utrzymuje ``aktualna_jednostka`` nie-NULL i samo JEST odpięciem)
    oraz zakończone. Bez tego drugiego, aktywnego AJ trigger
    ``bpp_autor_ustaw_jednostka_aktualna`` po wstawieniu samego zakończonego AJ
    (brak aktywnych) ZERUJE ``aktualna_jednostka`` (gałąź ELSE) — wynik ``[]``
    zostałby wtedy osiągnięty przez kryterium ``aktualna_jednostka=None``, więc
    regresja usunięcia ``exclude(zakonczyl_prace__lte=today)`` przeszłaby
    niezauważona. Aktywne AJ (nie-NULL ``aktualna_jednostka``) sprawia, że o
    wyniku decyduje TYLKO ``zakonczyl_prace``: aktywne MUSI być w zbiorze,
    zakończone — nie."""
    j_aktywne = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    j_zakonczone = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a = baker.make(Autor)
    aj_aktywne = baker.make(Autor_Jednostka, autor=a, jednostka=j_aktywne)
    aj_zakonczone = baker.make(
        Autor_Jednostka, autor=a, jednostka=j_zakonczone, zakonczyl_prace=yesterday
    )
    # Trigger AJ przelicza aktualną jednostkę po WSZYSTKICH AJ autora: aktywne
    # aj_aktywne utrzyma `aktualna_jednostka` = j_aktywne (nie-NULL) niezależnie
    # od kolejności wstawień.
    a.refresh_from_db()
    assert a.aktualna_jednostka_id is not None

    imp = baker.make(ImportPracownikow)
    zbior = set(imp.autorzy_spoza_pliku_set(today=today))
    assert aj_aktywne in zbior
    assert aj_zakonczone not in zbior


@pytest.mark.django_db
def test_wyklucza_obca_jednostke_uczelni(today):
    obca = baker.make(Jednostka, zarzadzaj_automatycznie=True)
    a = baker.make(Autor, aktualna_jednostka=obca)
    baker.make(Autor_Jednostka, autor=a, jednostka=obca)
    imp = baker.make(ImportPracownikow)

    class _Uczelnia:
        obca_jednostka_id = obca.pk

    assert list(imp.autorzy_spoza_pliku_set(uczelnia=_Uczelnia(), today=today)) == []
