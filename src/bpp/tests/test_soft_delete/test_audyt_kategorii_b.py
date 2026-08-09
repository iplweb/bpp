"""Kontrakt akcesorów wobec kosza (faza 03).

⚠️ KOREKTA 2026-08-08 (decyzja właściciela). Pierwsza wersja tej fazy kazała
akcesorom `rekord_w_bpp` / `get_bpp_publication` / `matchuj_publikacje`
ZAGLĄDAĆ DO KOSZA i zwracać skasowaną publikację. To był błąd i zostało
cofnięte.

Powód: soft-delete znaczy, że rekordu **nie ma**. `Rekord` (widok
`bpp_rekord_mat`) jest odfiltrowany po `deleted_at` już od fazy 01, i tak ma
zostać. Akcesor, który zwraca rzecz skasowaną, łamie kontrakt „`Rekord` albo
`None`", na którym stoją wszyscy jego konsumenci — m.in. admin PBN, który woła
`.original` (istniejące tylko na `Rekord`) i wywalał się `AttributeError` na
całej changeliście.

Zaglądanie do kosza jest decyzją **importera**, nie akcesora, i ma siedzieć
w ścieżce importu — tam, gdzie zapada.

Testy niżej przypinają kontrakt: skasowane = nieznalezione.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_get_bpp_publication_NIE_widzi_soft_deletowanego():
    """Skasowana publikacja jest dla akcesora NIEISTNIEJĄCA.

    To jest kontrakt, nie ograniczenie: `Rekord` to widok odfiltrowany po
    `deleted_at`, a `get_bpp_publication` ma zwracać `Rekord` albo `None`.
    Zwrócenie modelu konkretnego (co robiła pierwsza wersja fazy 03) wywalało
    admina PBN, bo ten woła `.original` — atrybut istniejący wyłącznie na
    `Rekord`.
    """
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    rec = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Testowy artykuł",
        rok=2020,
        pbn_uid=publication,
    )

    assert publication.get_bpp_publication() is not None, (
        "setup zepsuty — zywy rekord powinien byc znaleziony"
    )

    rec.delete()  # soft-delete

    assert publication.get_bpp_publication() is None, (
        "akcesor zwraca rekord z kosza — lamie kontrakt 'Rekord albo None'"
    )


@pytest.mark.django_db
def test_oswiadczenie_instytucji_get_bpp_publication_NIE_widzi_kosza():
    """Ta sama nazwa metody, INNY model — i też zostaje na `objects`.

    ⚠️ Łatwo pomylić z `Publication.get_bpp_publication` wyżej.
    `Oswiadczenie_Instytucji.get_bpp_publication` iteruje po czterech modelach
    publikacji po `pbn_uid`. Przy pierwszym audycie nie została rozstrzygnięta
    w ogóle — ani zmieniona, ani wpisana jako „zostawiona świadomie".

    ROZSTRZYGNIĘCIE (2026-08-09): zostaje na `objects`, bo to **akcesor**,
    a zaglądanie do kosza jest decyzją importera. Nie jest to jednak martwy
    przepis — łańcuch wołaczy realizuje wariant A w całości:

        `integruj_oswiadczenia...` (statements.py:404)
          → get_bpp_publication() zwraca None (rekord w koszu = "nie ma")
          → importuj_publikacje_instytucji(...)
          → importuj_publikacje_po_pbn_uid_id(...)
          → znajdz_lub_wskrzes_rekord()  ← TU rekord wraca z kosza

    Wołacz przyjmuje wynik obu kształtów: `Rekord` rozpakowuje przez
    `.original`, model konkretny (taki wraca ze wskrzeszenia) przepuszcza.
    Gdyby akcesor sam zaglądał do kosza, importer nigdy by się nie odpalił —
    i nie powstałby wpis w `RekordPrzywroconyPrzezImport`.
    """
    from pbn_api.models import OswiadczenieInstytucji, Publication

    publication = baker.make(Publication)
    rec = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)
    oswiadczenie = baker.make(OswiadczenieInstytucji, publicationId=publication)

    assert oswiadczenie.get_bpp_publication() is not None, (
        "setup zepsuty — zywy rekord powinien byc znaleziony"
    )

    rec.delete()  # soft-delete

    assert oswiadczenie.get_bpp_publication() is None, (
        "akcesor oswiadczenia widzi kosz — importer nigdy nie dostanie szansy "
        "wskrzesic rekordu i wpisac tego do rejestru"
    )


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
#   * `Oswiadczenie_Instytucji.get_bpp_publication`
#     (`pbn_api/models/oswiadczenie_instytucji.py`) — akcesor, nie importer;
#     wskrzeszanie robi wołacz o poziom wyżej. Dopisane 2026-08-09, bo przy
#     pierwszym audycie NIE zostało rozstrzygnięte w ogóle. Patrz test wyżej;
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
