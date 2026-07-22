"""Repro FD#407 — deduplikator autorów uwzględnia ``poprzednie_nazwiska``.

Gdy jedna osoba figuruje w bazie dwa razy pod różnymi nazwiskami (np. przed i
po zmianie nazwiska), a jeden z rekordów ma starą formę wpisaną w polu
``poprzednie_nazwiska``, deduplikator powinien skojarzyć te rekordy — również
gdy nazwiska nie mają wspólnego członu (panieńskie → po mężu).

Pokrywa obie fazy deduplikatora:
- general (all-pairs, meta-cache) — ``_run_general_phase``,
- PBN (anchored na OsobaZInstytucji) — ``szukaj_kopii``.
"""

import pytest
from model_bakery import baker

from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun
from deduplikator_autorow.utils import szukaj_kopii

# ---------------------------------------------------------------------------
# Faza general
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_general_laczy_zmiane_nazwiska_bez_wspolnego_czlonu():
    """Panieńskie → po mężu: "Kowalska" jako obecne u jednego rekordu i jako
    poprzednie u drugiego. Brak wspólnego członu → bez poprzednich nazwisk
    nie zostałyby nawet porównane."""
    a = baker.make(
        "bpp.Autor",
        nazwisko="Nowak",
        imiona="Anna",
        poprzednie_nazwiska="Kowalska",
    )
    b = baker.make("bpp.Autor", nazwisko="Kowalska", imiona="Anna")

    scan = DuplicateScanRun.objects.create()
    from deduplikator_autorow.tasks import _run_general_phase

    _run_general_phase(scan, min_confidence=50)

    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    assert cands.count() == 1
    cand = cands.get()
    assert {cand.main_autor_id, cand.duplicate_autor_id} == {a.pk, b.pk}


@pytest.mark.django_db
def test_general_laczy_po_wspolnym_poprzednim_nazwisku():
    """Dwa rekordy z różnymi obecnymi nazwiskami, ale wspólnym poprzednim."""
    a = baker.make(
        "bpp.Autor",
        nazwisko="Nowak",
        imiona="Maria",
        poprzednie_nazwiska="Panna",
    )
    b = baker.make(
        "bpp.Autor",
        nazwisko="Kowalski",
        imiona="Maria",
        poprzednie_nazwiska="Panna",
    )

    scan = DuplicateScanRun.objects.create()
    from deduplikator_autorow.tasks import _run_general_phase

    _run_general_phase(scan, min_confidence=50)

    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    assert cands.count() == 1
    assert {cands.get().main_autor_id, cands.get().duplicate_autor_id} == {a.pk, b.pk}


# ---------------------------------------------------------------------------
# Faza PBN (szukaj_kopii)
# ---------------------------------------------------------------------------


def test_szukaj_kopii_znajduje_po_poprzednim_nazwisku(
    osoba_z_instytucji, glowny_autor, autor_maker, tytuly
):
    """Kandydat, którego OBECNE nazwisko jest inne, ale w ``poprzednie_nazwiska``
    ma nazwisko głównego autora (Gal-Cisoń) — powinien zostać znaleziony."""
    duplikat = autor_maker(
        imiona="Jan",
        nazwisko="Zawadzka",
        poprzednie_nazwiska="Gal-Cisoń",
    )

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    assert duplikat in duplikaty
