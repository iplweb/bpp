"""Zakresy wyszukiwania autora na ``AutorQuerySet`` (spec 2026-07-02).

Zakresy jako czytelne API managera:
- ``aktualnie_zatrudnieni(uczelnia)`` — aktualna jednostka w uczelni, realna
  (``skupia_pracownikow=True``),
- ``kiedykolwiek_zatrudnieni(uczelnia)`` — obecnie LUB historycznie, ale tylko
  przez realną jednostkę (``skupia_pracownikow=True``); pomija jednostki obce,
- ``kiedykolwiek_zwiazani(uczelnia)`` — obecnie LUB historycznie, dowolna
  jednostka (także obca),
- WSZYSCY = ``Autor.objects.all()`` (bez metody).
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Autor
from bpp.models.autor import Autor_Jednostka
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu


def _wpis_historyczny(autor, jednostka):
    """Zakończone zatrudnienie: trigger 0046 pozostawia aktualna_jednostka=None,
    więc autor jest TYLKO historycznie związany (nie aktualnie zatrudniony)."""
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=timezone.now() - timedelta(days=60),
        zakonczyl_prace=timezone.now() - timedelta(days=30),
    )
    autor.refresh_from_db()
    assert autor.aktualna_jednostka is None  # sanity: trigger nie ustawił


@pytest.fixture
def obca_jednostka_uczelni(uczelnia, wydzial):
    """Jednostka techniczna/obca uczelni — nie skupia pracowników."""
    return baker.make(
        "bpp.Jednostka",
        uczelnia=uczelnia,
        parent=znajdz_lub_utworz_wezel_wydzialu(wydzial)[0],
        skupia_pracownikow=False,
    )


@pytest.mark.django_db
def test_aktualnie_zatrudnieni_zwraca_autora_z_realnej_jednostki(uczelnia, jednostka):
    autor = baker.make(Autor, aktualna_jednostka=jednostka)  # skupia_pracownikow=True

    wynik = Autor.objects.aktualnie_zatrudnieni(uczelnia)

    assert autor in wynik


@pytest.mark.django_db
def test_aktualnie_zatrudnieni_pomija_jednostke_obca(uczelnia, obca_jednostka_uczelni):
    autor = baker.make(Autor, aktualna_jednostka=obca_jednostka_uczelni)

    wynik = Autor.objects.aktualnie_zatrudnieni(uczelnia)

    assert autor not in wynik


@pytest.mark.django_db
def test_aktualnie_zatrudnieni_pomija_tylko_historycznie_zwiazanego(
    uczelnia, jednostka
):
    autor = baker.make(Autor, aktualna_jednostka=None)
    _wpis_historyczny(autor, jednostka)

    wynik = Autor.objects.aktualnie_zatrudnieni(uczelnia)

    assert autor not in wynik


@pytest.mark.django_db
def test_kiedykolwiek_zwiazani_zwraca_tylko_historycznego(uczelnia, jednostka):
    autor = baker.make(Autor, aktualna_jednostka=None)
    _wpis_historyczny(autor, jednostka)

    wynik = Autor.objects.kiedykolwiek_zwiazani(uczelnia)

    assert autor in wynik


@pytest.mark.django_db
def test_kiedykolwiek_zwiazani_zwraca_aktualnie_zatrudnionego(uczelnia, jednostka):
    autor = baker.make(Autor, aktualna_jednostka=jednostka)

    wynik = Autor.objects.kiedykolwiek_zwiazani(uczelnia)

    assert autor in wynik


@pytest.mark.django_db
def test_kiedykolwiek_zwiazani_bez_duplikatow(uczelnia, jednostka):
    """Autor aktualny ORAZ z wieloma wpisami historycznymi = jeden wiersz."""
    autor = baker.make(Autor, aktualna_jednostka=jednostka)
    # Rozne daty rozpoczecia: wpisy sa legalne wobec czesciowego constraintu
    # ``bpp_autor_jednostka_bez_daty_unikalne`` (obejmuje wylacznie wiersze z
    # NULL-owym ``rozpoczal_prace``), a test dalej sprawdza dokladnie to, co
    # sprawdzal — ze zakres nie duplikuje autora przy wielu powiazaniach.
    baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
    )
    baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2015, 1, 1),
    )

    wynik = list(Autor.objects.kiedykolwiek_zwiazani(uczelnia))

    assert wynik.count(autor) == 1


@pytest.mark.django_db
def test_kiedykolwiek_zatrudnieni_zwraca_aktualnie_zatrudnionego(uczelnia, jednostka):
    autor = baker.make(Autor, aktualna_jednostka=jednostka)  # skupia_pracownikow=True

    wynik = Autor.objects.kiedykolwiek_zatrudnieni(uczelnia)

    assert autor in wynik


@pytest.mark.django_db
def test_kiedykolwiek_zatrudnieni_zwraca_historycznie_zatrudnionego(
    uczelnia, jednostka
):
    """Kluczowa różnica względem ``aktualnie_zatrudnieni``: autor związany z
    realną jednostką uczelni TYLKO w przeszłości też się łapie."""
    autor = baker.make(Autor, aktualna_jednostka=None)
    _wpis_historyczny(autor, jednostka)

    wynik = Autor.objects.kiedykolwiek_zatrudnieni(uczelnia)

    assert autor in wynik


@pytest.mark.django_db
def test_kiedykolwiek_zatrudnieni_pomija_aktualna_jednostke_obca(
    uczelnia, obca_jednostka_uczelni
):
    """Aktualna jednostka obca (``skupia_pracownikow=False``) NIE kwalifikuje,
    nawet gdy należy do bieżącej uczelni (lustrzana jednostka obca)."""
    autor = baker.make(Autor, aktualna_jednostka=obca_jednostka_uczelni)

    wynik = Autor.objects.kiedykolwiek_zatrudnieni(uczelnia)

    assert autor not in wynik


@pytest.mark.django_db
def test_kiedykolwiek_zatrudnieni_pomija_tylko_historycznie_w_jednostce_obcej(
    uczelnia, obca_jednostka_uczelni
):
    """Powiązanie WYŁĄCZNIE przez historyczną jednostkę obcą nie łapie autora —
    to główny przypadek, który odróżnia ``kiedykolwiek_zatrudnieni`` od
    ``kiedykolwiek_zwiazani`` (ta druga by go zwróciła)."""
    autor = baker.make(Autor, aktualna_jednostka=None)
    _wpis_historyczny(autor, obca_jednostka_uczelni)

    assert autor not in Autor.objects.kiedykolwiek_zatrudnieni(uczelnia)
    assert autor in Autor.objects.kiedykolwiek_zwiazani(uczelnia)


@pytest.mark.django_db
def test_kiedykolwiek_zatrudnieni_realna_jednostka_wygrywa_nad_obca(
    uczelnia, jednostka, obca_jednostka_uczelni
):
    """Autor z historią i w realnej, i w obcej jednostce — łapie się przez
    realną (bez duplikatów)."""
    autor = baker.make(Autor, aktualna_jednostka=None)
    _wpis_historyczny(autor, obca_jednostka_uczelni)
    _wpis_historyczny(autor, jednostka)

    wynik = list(Autor.objects.kiedykolwiek_zatrudnieni(uczelnia))

    assert wynik.count(autor) == 1


@pytest.mark.django_db
def test_kiedykolwiek_zatrudnieni_izolacja_miedzy_uczelniami(uczelnia, jednostka):
    """Realna jednostka historyczna INNEJ uczelni nie łapie autora."""
    from bpp.models import Uczelnia

    druga = baker.make(Uczelnia, skrot="U2", nazwa="Druga uczelnia")
    druga_jednostka = baker.make(
        "bpp.Jednostka", uczelnia=druga, skupia_pracownikow=True
    )
    autor = baker.make(Autor, aktualna_jednostka=None)
    _wpis_historyczny(autor, druga_jednostka)

    assert autor not in Autor.objects.kiedykolwiek_zatrudnieni(uczelnia)


@pytest.mark.django_db
def test_uczelnia_none_fail_closed(jednostka):
    """Brak ustalonej uczelni → pusty queryset (nie fail-open)."""
    baker.make(Autor, aktualna_jednostka=jednostka)

    assert not Autor.objects.aktualnie_zatrudnieni(None).exists()
    assert not Autor.objects.kiedykolwiek_zwiazani(None).exists()
    assert not Autor.objects.kiedykolwiek_zatrudnieni(None).exists()


@pytest.mark.django_db
def test_lancuch_fulltext_plus_zakres(uczelnia, jednostka):
    """``fulltext_filter(q).kiedykolwiek_zwiazani(u)`` zawęża i po tekście, i po zakresie."""
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka)
    baker.make(Autor, nazwisko="Nowak", imiona="Anna", aktualna_jednostka=jednostka)

    wynik = Autor.objects.fulltext_filter("Kowalski").kiedykolwiek_zwiazani(uczelnia)

    nazwiska = {a.nazwisko for a in wynik}
    assert nazwiska == {"Kowalski"}


@pytest.mark.django_db
def test_aktualnie_zatrudnieni_izolacja_miedzy_uczelniami(uczelnia, jednostka):
    """Multi-host: zakres 1 dla uczelni A nie zwraca autora zatrudnionego w B."""
    from bpp.models import Uczelnia

    druga = baker.make(Uczelnia, skrot="U2", nazwa="Druga uczelnia")
    druga_jednostka = baker.make(
        "bpp.Jednostka", uczelnia=druga, skupia_pracownikow=True
    )

    autor_a = baker.make(Autor, aktualna_jednostka=jednostka)
    autor_b = baker.make(Autor, aktualna_jednostka=druga_jednostka)

    wynik = Autor.objects.aktualnie_zatrudnieni(uczelnia)

    assert autor_a in wynik
    assert autor_b not in wynik
