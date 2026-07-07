"""Faza C / issue #438 — backfill ``poprzednie_nazwy`` (migracja 0466).

PRZED usunięciem modelu ``Wydzial`` (0467) migracja 0466 dopisuje nazwę każdego
wydziału do ``poprzednie_nazwy`` jego węzła-korzenia (po ``legacy_wydzial_id``),
aby matchowanie importu (``matchuj_wydzial``, T1) dalej odnajdywało root po
dawnej nazwie wydziału — nawet gdy root został PROMOWANY z realnej jednostki
i nosi jej nazwę, a nie nazwę wydziału.

Testujemy CZYSTĄ logikę scalania (``nowa_poprzednie_nazwy``), a nie przejście
przez ORM — model ``Wydzial`` i tabela ``bpp_wydzial`` nie istnieją już w
zmigrowanej bazie testowej (0467), więc nie da się ich tu utworzyć.
"""

from importlib import import_module

_mig = import_module("bpp.migrations.0466_faza_c_backfill_poprzednie_nazwy")
_nowa = _mig.nowa_poprzednie_nazwy


def test_dopisuje_nazwe_wydzialu_do_promowanego_roota():
    # root promowany nosi nazwę realnej jednostki → nazwa wydziału dochodzi
    assert (
        _nowa("", "Wydział Nauk Ścisłych", "Katedra Fizyki")
        == "Wydział Nauk Ścisłych"
    )


def test_dokłada_a_nie_nadpisuje_istniejacych():
    wynik = _nowa("Dawna Nazwa Historyczna", "Wydział Farmaceutyczny", "Kolegium")
    assert "Dawna Nazwa Historyczna" in wynik
    assert "Wydział Farmaceutyczny" in wynik
    assert wynik.splitlines() == ["Dawna Nazwa Historyczna", "Wydział Farmaceutyczny"]


def test_idempotentny_gdy_juz_wpisana():
    assert _nowa("Wydział Prawa", "Wydział Prawa", "Instytut X") is None


def test_idempotentny_case_insensitive():
    assert _nowa("wydział prawa", "Wydział Prawa", "Instytut X") is None


def test_pomija_gdy_nazwa_roota_rowna_wydzialowi():
    # węzeł-lustro: nazwa roota == nazwa wydziału → match po nazwa__iexact
    assert _nowa("", "Wydział Lekarski", "Wydział Lekarski") is None


def test_pomija_gdy_nazwa_roota_rowna_case_insensitive():
    assert _nowa("", "Wydział Lekarski", "wydział lekarski") is None


def test_pomija_pusta_nazwe_wydzialu():
    assert _nowa("cokolwiek", "", "Root") is None
    assert _nowa("cokolwiek", "   ", "Root") is None
    assert _nowa("cokolwiek", None, "Root") is None


def test_pomija_gdy_przepelnia_kolumne():
    dlugie = "x" * 4090
    # dołożenie "Wydział ..." przekroczyłoby 4096 → brak zmiany
    assert _nowa(dlugie, "Wydział Bardzo Długiej Nazwy", "Root") is None
