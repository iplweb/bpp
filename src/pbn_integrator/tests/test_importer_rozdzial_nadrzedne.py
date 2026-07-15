"""Import rozdziału musi znosić wyd. nadrzędne bez powiązania z PBN.

Geneza (Rollbar, batch apoz.edu.pl 2026-06-29):
- #419 ``AttributeError: 'NoneType' object has no attribute 'current_version'``
  (3x) — książka nadrzędna rozdziału została dopasowana do istniejącego rekordu
  BPP przez fuzzy-match (bez ``pbn_uid``). Kod robił wprost
  ``wydawnictwo_nadrzedne.pbn_uid.current_version[...]`` i wywalał się na
  ``pbn_uid is None``.

``_chapter_json_z_nadrzednego`` degraduje do pustego słownika, gdy nadrzędne nie
ma ``pbn_uid`` albo wersji bieżącej — rozdział importuje się z metadanych
własnych, bez sub-słownika z nadrzędnego.
"""

from types import SimpleNamespace

from pbn_integrator.importer.chapters import _chapter_json_z_nadrzednego


def test_bez_pbn_uid_zwraca_pusty_dict():
    """Nadrzędne bez ``pbn_uid`` (fuzzy-match) → ``{}`` zamiast AttributeError."""
    nadrzedne = SimpleNamespace(pbn_uid=None)

    assert _chapter_json_z_nadrzednego(nadrzedne, "m1") == {}


def test_pbn_uid_bez_wersji_biezacej_zwraca_pusty_dict():
    """Nadrzędne z ``pbn_uid``, ale bez wersji bieżącej → ``{}``."""
    nadrzedne = SimpleNamespace(pbn_uid=SimpleNamespace(current_version=None))

    assert _chapter_json_z_nadrzednego(nadrzedne, "m1") == {}


def test_zwraca_subdict_rozdzialu_gdy_obecny():
    """Kontrola: gdy nadrzędne ma sub-słownik rozdziału — zwracamy go."""
    nadrzedne = SimpleNamespace(
        pbn_uid=SimpleNamespace(
            current_version={"object": {"chapters": {"m1": {"pagesFromTo": "1-10"}}}}
        )
    )

    assert _chapter_json_z_nadrzednego(nadrzedne, "m1") == {"pagesFromTo": "1-10"}


def test_brak_mongoid_w_chapters_zwraca_pusty_dict():
    """Nadrzędne bez wpisu dla tego rozdziału w ``chapters`` → ``{}``."""
    nadrzedne = SimpleNamespace(
        pbn_uid=SimpleNamespace(current_version={"object": {"chapters": {}}})
    )

    assert _chapter_json_z_nadrzednego(nadrzedne, "m1") == {}
