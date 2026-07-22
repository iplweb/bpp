"""Testy funkcji `_zaktualizuj_liczbe_cytowan` (aktualizacja pól z WoS).

Mapowanie kluczy (zachowane):

    item["timesCited"] -> obj.liczba_cytowan
    item["pmid"]       -> obj.pubmed_id
    item["doi"]        -> obj.doi

Guard każdego pola: wartość `is not None` ORAZ różna od bieżącej. Funkcja nic
nie zwraca (None).

Po refaktorze (#8 security review): tylko rekordy z DOI+PMID trafiają do
korpusu odpytywanego w WoS (bez identyfikatora nie ma czego szukać), a zapis
idzie hurtowo przez ``bulk_update`` (NIE ``save()`` per rekord).
"""

from unittest.mock import Mock

import pytest
from model_bakery import baker

from bpp.models import Uczelnia, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.tasks import _zaktualizuj_liczbe_cytowan


def _patch_wosclient(mocker, payload):
    """Podstaw klienta WoS, którego query_multiple zwraca `payload`."""
    client = Mock()
    client.query_multiple = Mock(return_value=payload)
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=client)
    return client


@pytest.mark.django_db
def test_aktualizuje_wszystkie_pola_gdy_inne(uczelnia, wydawnictwo_ciagle, mocker):
    # Rekord musi mieć DOI+PMID, żeby wszedł do korpusu WoS; liczba_cytowan
    # jeszcze nieznana. WoS zwraca nowe wartości wszystkich trzech pól.
    wydawnictwo_ciagle.liczba_cytowan = None
    wydawnictwo_ciagle.pubmed_id = 111
    wydawnictwo_ciagle.doi = "10.0/old"
    wydawnictwo_ciagle.save()

    _patch_wosclient(
        mocker,
        [
            {
                wydawnictwo_ciagle.pk: {
                    "timesCited": 42,
                    "pmid": 123456,
                    "doi": "10.1234/abc",
                }
            }
        ],
    )

    _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle])

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 42
    assert wydawnictwo_ciagle.pubmed_id == 123456
    assert wydawnictwo_ciagle.doi == "10.1234/abc"


@pytest.mark.django_db
def test_nie_aktualizuje_pol_gdy_wartosc_none(uczelnia, wydawnictwo_ciagle, mocker):
    wydawnictwo_ciagle.liczba_cytowan = 7
    wydawnictwo_ciagle.pubmed_id = 999
    wydawnictwo_ciagle.doi = "10.9999/keep"
    wydawnictwo_ciagle.save()

    # Pusty słownik -> wszystkie .get(...) zwracają None -> nic nie ruszamy.
    _patch_wosclient(mocker, [{wydawnictwo_ciagle.pk: {}}])

    spy = mocker.spy(Wydawnictwo_Ciagle, "save")

    _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle])

    spy.assert_not_called()
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 7
    assert wydawnictwo_ciagle.pubmed_id == 999
    assert wydawnictwo_ciagle.doi == "10.9999/keep"


@pytest.mark.django_db
def test_nie_zapisuje_gdy_wartosci_rowne(uczelnia, wydawnictwo_ciagle, mocker):
    wydawnictwo_ciagle.liczba_cytowan = 5
    wydawnictwo_ciagle.pubmed_id = 111
    wydawnictwo_ciagle.doi = "10.1/same"
    wydawnictwo_ciagle.save()

    _patch_wosclient(
        mocker,
        [
            {
                wydawnictwo_ciagle.pk: {
                    "timesCited": 5,
                    "pmid": 111,
                    "doi": "10.1/same",
                }
            }
        ],
    )

    spy = mocker.spy(Wydawnictwo_Ciagle, "save")

    _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle])

    # Identyczne wartości -> changed pozostaje False -> brak save().
    spy.assert_not_called()


@pytest.mark.django_db
def test_aktualizuje_tylko_rozne_pole(uczelnia, wydawnictwo_ciagle, mocker):
    wydawnictwo_ciagle.liczba_cytowan = 5
    wydawnictwo_ciagle.pubmed_id = 111
    wydawnictwo_ciagle.doi = "10.1/orig"
    wydawnictwo_ciagle.save()

    # Tylko liczba_cytowan się różni; pmid/doi takie same.
    _patch_wosclient(
        mocker,
        [
            {
                wydawnictwo_ciagle.pk: {
                    "timesCited": 99,
                    "pmid": 111,
                    "doi": "10.1/orig",
                }
            }
        ],
    )

    _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle])

    # Zapis hurtowy (bulk_update) — sprawdzamy stan w bazie, nie wywołanie save().
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 99
    assert wydawnictwo_ciagle.pubmed_id == 111
    assert wydawnictwo_ciagle.doi == "10.1/orig"


@pytest.mark.django_db
def test_obsluguje_wiele_typow_modeli(
    uczelnia, wydawnictwo_ciagle, wydawnictwo_zwarte, mocker
):
    # Oba rekordy z DOI+PMID (żeby weszły do korpusu WoS), liczba_cytowan pusta.
    wydawnictwo_ciagle.liczba_cytowan = None
    wydawnictwo_ciagle.doi = "10.1/c"
    wydawnictwo_ciagle.pubmed_id = 1
    wydawnictwo_ciagle.save()
    wydawnictwo_zwarte.liczba_cytowan = None
    wydawnictwo_zwarte.doi = "10.1/z"
    wydawnictwo_zwarte.pubmed_id = 2
    wydawnictwo_zwarte.save()

    # Druga uczelnia = dwa klienty WoS → `query_multiple` woła się RAZ NA KLIENTA
    # na typ (patrz `_pobierz_wyniki_wos`). Odwzorowuje realny scenariusz z CI:
    # test Playwright (transaction=True) w tym samym shardzie zostawia
    # zacommitowany rekord Uczelnia, więc `Uczelnia.objects.all()` zwraca >1 →
    # więcej wywołań klienta. Sztywna `side_effect`-lista pękłaby (StopIteration);
    # mock MUSI być odporny na liczbę wywołań.
    baker.make(Uczelnia)

    client = Mock()

    def _cytowania_wos(rekordy, *args, **kwargs):
        # `rekordy` = korpus JEDNEGO typu (lista {"id","doi","pubmed_id"}),
        # więc zwracamy cytowania tylko dla pk-ów obecnych w tym zapytaniu
        # (bez kolizji między typami) i ignorujemy ewentualne obce rekordy.
        cytowania = {
            wydawnictwo_ciagle.pk: {"timesCited": 11},
            wydawnictwo_zwarte.pk: {"timesCited": 22},
        }
        ids = {r["id"] for r in rekordy}
        grp = {pk: dane for pk, dane in cytowania.items() if pk in ids}
        return [grp] if grp else []

    client.query_multiple = Mock(side_effect=_cytowania_wos)
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=client)

    _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle, Wydawnictwo_Zwarte])

    wydawnictwo_ciagle.refresh_from_db()
    wydawnictwo_zwarte.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 11
    assert wydawnictwo_zwarte.liczba_cytowan == 22


@pytest.mark.django_db
def test_zwraca_none(uczelnia, wydawnictwo_ciagle, mocker):
    _patch_wosclient(mocker, [{wydawnictwo_ciagle.pk: {"timesCited": 1}}])

    result = _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle])

    assert result is None
