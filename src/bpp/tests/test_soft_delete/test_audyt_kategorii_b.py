"""Kategoria B: miejsca, które MUSZĄ widzieć rekordy w koszu (faza 03).

Po fazie 02 domyślny menedżer publikacji ukrywa soft-skasowane wiersze —
i dla większości kodu jest to zachowanie właściwe („kategoria A", czysta
automatycznie). Kategoria B to wyjątki: matching podczas re-importu
i deduplikacji. Jeśli te miejsca użyją ukrywającego menedżera, skasowany
rekord staje się NIEWIDZIALNY i importer tworzy DUPLIKAT — czyli dokładnie
ten skutek, dla którego handoff fazy 02 nazywa fazę 03 obowiązkową razem z 02.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_get_bpp_publication_widzi_soft_deletowany_rekord():
    """Matching po ``pbn_uid`` MUSI znaleźć soft-skasowaną publikację.

    ``pbn_api.Publication.rekord_w_bpp`` szuka przez ``Rekord`` — a to widok
    (``bpp_rekord_mat``), przefiltrowany po ``deleted_at`` już w fazie 01.
    Skasowany rekord z niego znika, więc matching zwraca ``None`` i importer
    zakłada, że publikacji nie ma.
    """
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    rec = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Testowy artykuł",
        rok=2020,
        pbn_uid=publication,
    )
    rec.delete()  # soft-delete

    assert Wydawnictwo_Ciagle.objects.filter(pk=rec.pk).count() == 0
    assert Wydawnictwo_Ciagle.global_objects.filter(pk=rec.pk).count() == 1

    znaleziony = publication.get_bpp_publication()
    assert znaleziony is not None, (
        "matching po pbn_uid musi widzieć soft-deletowany rekord"
    )
    assert znaleziony.pk == rec.pk


@pytest.mark.django_db
def test_matchuj_publikacje_po_tytule_widzi_soft_deletowany():
    """Fuzzy matching importu musi znaleźć soft-skasowaną publikację.

    Inaczej re-import „nie widzi" rekordu, tworzy go od nowa — i baza dostaje
    duplikat, którego operator nie zobaczy, bo oryginał siedzi w koszu.
    """
    from import_common.core.publikacja import matchuj_publikacje

    rec = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Unikalny tytul do matchowania importu",
        rok=2019,
    )
    rec.delete()

    wynik = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Unikalny tytul do matchowania importu",
        year=2019,
    )

    assert wynik is not None, (
        "fuzzy matching nie widzi soft-deletowanego rekordu -> re-import "
        "utworzy duplikat"
    )
    assert wynik.pk == rec.pk


@pytest.mark.django_db
def test_matchuj_publikacje_po_doi_widzi_soft_deletowany():
    """To samo dla DOI.

    ⚠️ Tytuł MUSI być zgodny, mimo że matchujemy po DOI:
    ``_try_match_pub_by_doi`` zawęża co prawda po DOI, ale kandydata i tak
    przepuszcza przez próg podobieństwa tytułu (0.80). Pierwsza wersja tego
    testu podawała celowo inny tytuł i padała — nie dlatego, że kod nie widzi
    kosza, tylko dlatego, że tak działa matching. Wartość testu jest w tym,
    żeby mierzył widoczność kosza, a nie regułę podobieństwa.
    """
    from import_common.core.publikacja import matchuj_publikacje

    tytul = "Publikacja z DOI do matchowania importu"
    rec = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=tytul,
        rok=2021,
        doi="10.1234/test.soft.delete",
    )
    rec.delete()

    wynik = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title=tytul,
        year=2021,
        doi="10.1234/test.soft.delete",
    )

    assert wynik is not None, "matching po DOI nie widzi kosza"
    assert wynik.pk == rec.pk
