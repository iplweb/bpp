"""Repro dla FD#422 — zdublowane źródło niedopasowane przy imporcie z CrossRef.

Zgłoszenie opisywało, że źródło „Zeszyty Naukowe SGSP" (praca „NOISE IN THE
COCKPIT OF THE AT-3 R100 TRAINING AIRCRAFT IN …", DOI
10.5604/01.3001.0055.7096) nie dopasowuje się przy imporcie z CrossRef.

Faktyczna przyczyna NIE leży w dopisku skrótu w nawiasie (CrossRef zwraca
czyste ``container-title`` = „Zeszyty Naukowe SGSP", a „ZN SGSP" to osobne
``short-container-title"). Przyczyną są **zdublowane rekordy źródła** o
identycznej nazwie w bazie (na instancji apoz: id 170 i 74291, oba „Zeszyty
Naukowe SGSP", oba ISSN 0239-5223).

Wyszukiwanie trygramowe zwraca wtedy >1 rekord, a
``WynikPorownania.rekord_po_stronie_bpp`` zwraca rekord tylko gdy jest
DOKŁADNIE jeden — przy duplikatach oddaje ``None`` i źródło zostaje puste.
Naprawą jest scalanie duplikatów o tej samej (znormalizowanej) nazwie do
jednego reprezentanta (rekord o najniższym pk = pierwotny).
"""

import pytest
from model_bakery import baker

from bpp.models import Zrodlo
from crossref_bpp.core import Komparator
from import_common.core import normalize_zrodlo_nazwa_for_db_lookup


@pytest.mark.django_db
def test_porownaj_container_title_zdublowane_zrodlo():
    # Dwa zdublowane źródła o identycznej nazwie (realny stan bazy apoz).
    z1 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")
    z2 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")
    pierwotny = min((z1, z2), key=lambda z: z.pk)

    wynik = Komparator.porownaj_container_title("Zeszyty Naukowe SGSP")

    # Przed naprawą: trygram zwraca 2 rekordy → rekord_po_stronie_bpp = None.
    # Po naprawie: duplikaty scalają się do rekordu pierwotnego.
    assert wynik.rekord_po_stronie_bpp == pierwotny


@pytest.mark.django_db
def test_porownaj_short_container_title_zdublowane_zrodlo():
    # To samo dla dopasowania po skrócie (short-container-title → skrot).
    z1 = baker.make(Zrodlo, skrot="ZN SGSP")
    z2 = baker.make(Zrodlo, skrot="ZN SGSP")
    pierwotny = min((z1, z2), key=lambda z: z.pk)

    wynik = Komparator.porownaj_short_container_title("ZN SGSP")

    assert wynik.rekord_po_stronie_bpp == pierwotny


@pytest.mark.django_db
def test_scal_duplikaty_zrodel_nie_scala_roznych_zrodel():
    # Realnie różne źródła nie mogą zostać scalone — to prawdziwa
    # niejednoznaczność, a nie duplikat.
    z1 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")
    z2 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")
    inny = baker.make(Zrodlo, nazwa="Zeszyty Naukowe AGH")

    scalone = Komparator._scal_duplikaty_zrodel(
        [z2, z1, inny], "nazwa", normalize_zrodlo_nazwa_for_db_lookup
    )

    # Duplikaty SGSP → jeden reprezentant (niższe pk); różne źródło zostaje.
    assert len(scalone) == 2
    sgsp = [z for z in scalone if z.nazwa == "Zeszyty Naukowe SGSP"]
    assert len(sgsp) == 1
    assert sgsp[0].pk == min(z1.pk, z2.pk)
    assert inny in scalone
