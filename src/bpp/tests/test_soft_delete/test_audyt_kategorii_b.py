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


# ---------------------------------------------------------------------------
# REJESTR DECYZJI AUDYTU (Task 7) — miejsca ZOSTAWIONE na `objects`
# ---------------------------------------------------------------------------
#
# Reguła nadrzędna: default „pomijaj skasowane" jest tu ZNACZNIE bezpieczniejszy
# niż odwrotny. Zmieniamy wyłącznie miejsca, które MUSZĄ widzieć kosz, żeby nie
# zostawić sierot albo nie zgubić transferu. Poniższe zostają bez zmian —
# świadomie, a nie przez przeoczenie:
#
#   * ewaluacja (`ewaluacja_optymalizacja/**`, `ewaluacja_dwudyscyplinowcy`) —
#     praca w koszu nie bierze udziału w punktacji ani optymalizacji;
#   * snapshot odpięć (`snapshot_odpiec`) — praca w koszu to brak odpięcia do
#     zapisania;
#   * komparator PBN (`komparator_pbn/views.py`) — soft-delete wycofuje
#     oświadczenia z PBN (faza 05), więc BPP tej pracy już nie deklaruje;
#     `objects` daje obraz spójny z PBN;
#   * REST API (`api_v1/viewsets/*`) — publiczne API nie może serwować autorstw
#     pracy, która sama z API zniknęła;
#   * skanowanie do dedupu publikacji (`deduplikator_publikacji/tasks.py`) —
#     patrz test niżej.
#
# ⚠️ Wszystkie `.update()` w tych miejscach dotyczą `przypieta`,
# `dyscyplina_naukowa` i `afiliuje` — NIE `deleted_at`, więc gate
# `BppSoftDeleteQuerySet.update()` z fazy 01 się nie odpala. Sprawdzone.


@pytest.mark.django_db
def test_dedup_publikacji_NIE_widzi_kosza():
    """Skanowanie do deduplikacji ma pomijać kosz — i to jest poprawne.

    Rekord skasowany nie jest duplikatem do rozstrzygnięcia; podsuwanie go
    operatorowi kazałoby mu scalać rzecz, którą sam usunął. To odwrotna
    decyzja niż przy matchingu importu (który MUSI widzieć kosz, żeby nie
    tworzyć duplikatów) — i właśnie dlatego jest tu przypięta testem, a nie
    zostawiona jako „oczywista".
    """
    from deduplikator_publikacji.tasks import _get_publications_to_scan

    zywa = baker.make(Wydawnictwo_Ciagle, rok=2020)
    kosz = baker.make(Wydawnictwo_Ciagle, rok=2020)
    kosz.delete()

    zebrane = {pub.pk for _ct, pub in _get_publications_to_scan(2020, 2020)}

    assert zywa.pk in zebrane
    assert kosz.pk not in zebrane, "dedup podsuwa operatorowi rekord z kosza"


@pytest.mark.django_db
def test_transfer_przy_scalaniu_autorow_widzi_kosz():
    """Scalanie autorów MUSI przenieść też autorstwa w koszu.

    Inaczej zostają SIEROTY: wiersze wskazujące na autora-duplikat, który po
    scaleniu ma zniknąć. W fazie 04 zablokują dodatkowo guard PROTECT — czyli
    problem ujawniłby się dopiero tam, w miejscu niezwiązanym z przyczyną.
    """
    from bpp.models import Autor, Wydawnictwo_Ciagle_Autor
    from deduplikator_autorow.utils.merge import wiersze_do_transferu

    duplikat = baker.make(Autor)
    wc = baker.make(Wydawnictwo_Ciagle)
    zywe = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=duplikat, kolejnosc=0)
    skasowane = baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wc, autor=duplikat, kolejnosc=1
    )
    skasowane.delete()

    do_transferu = {
        x.pk for x in wiersze_do_transferu(Wydawnictwo_Ciagle_Autor, duplikat)
    }

    assert zywe.pk in do_transferu
    assert skasowane.pk in do_transferu, (
        "autorstwo w koszu nie zostanie przeniesione -> sierota przy duplikacie"
    )
