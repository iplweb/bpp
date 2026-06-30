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
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from crossref_bpp.core import Komparator
from crossref_bpp.duplikaty import ostrzez_o_zduplikowanych_zrodlach
from import_common.core import normalize_zrodlo_nazwa_for_db_lookup


def _request_z_messages():
    request = RequestFactory().get("/")
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


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

    scalone, blokujace = Komparator._scal_duplikaty_zrodel(
        [z2, z1, inny], "nazwa", normalize_zrodlo_nazwa_for_db_lookup
    )

    # Duplikaty SGSP → jeden reprezentant (niższe pk); różne źródło zostaje.
    assert len(scalone) == 2
    sgsp = [z for z in scalone if z.nazwa == "Zeszyty Naukowe SGSP"]
    assert len(sgsp) == 1
    assert sgsp[0].pk == min(z1.pk, z2.pk)
    assert inny in scalone
    assert blokujace == []  # ten sam (pusty) ISSN → scalone, nie blokują


@pytest.mark.django_db
def test_scal_duplikaty_zrodel_rozne_issn_nie_scalane():
    # Ta sama nazwa, ale różne niepuste ISSN-y = różne czasopisma.
    # Nie wolno ich scalić — niejednoznaczność trafia w ręczny wybór.
    z1 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe", issn="1111-1111")
    z2 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe", issn="2222-2222")

    scalone, blokujace = Komparator._scal_duplikaty_zrodel(
        [z1, z2], "nazwa", normalize_zrodlo_nazwa_for_db_lookup
    )

    assert set(scalone) == {z1, z2}
    # Konflikt ISSN → te rekordy blokują dopasowanie (→ deduplikator).
    assert set(blokujace) == {z1, z2}


@pytest.mark.django_db
def test_porownaj_container_title_konflikt_issn_zglasza_duplikaty():
    # Dwa różne czasopisma o tej samej nazwie (różne ISSN) blokują
    # jednoznaczne dopasowanie i są raportowane jako zduplikowane.
    z1 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe", issn="1111-1111")
    z2 = baker.make(Zrodlo, nazwa="Zeszyty Naukowe", issn="2222-2222")

    wynik = Komparator.porownaj_container_title("Zeszyty Naukowe")

    assert wynik.rekord_po_stronie_bpp is None
    assert set(wynik.zduplikowane_zrodla) == {z1, z2}


@pytest.mark.django_db
def test_porownaj_container_title_scalone_duplikaty_nie_blokuja():
    # Prawdziwe duplikaty (ten sam/pusty ISSN) są scalane i NIE są
    # raportowane jako blokujące — dopasowanie się udaje.
    baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")
    baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")

    wynik = Komparator.porownaj_container_title("Zeszyty Naukowe SGSP")

    assert wynik.rekord_po_stronie_bpp is not None
    assert wynik.zduplikowane_zrodla == []


@pytest.mark.django_db
def test_ostrzez_o_zduplikowanych_zrodlach_dodaje_link_do_deduplikatora():
    baker.make(Zrodlo, nazwa="Zeszyty Naukowe", issn="1111-1111")
    baker.make(Zrodlo, nazwa="Zeszyty Naukowe", issn="2222-2222")
    wynik = Komparator.porownaj_container_title("Zeszyty Naukowe")

    request = _request_z_messages()
    ostrzez_o_zduplikowanych_zrodlach(request, wynik)

    msgs = [str(m) for m in request._messages]
    assert len(msgs) == 1
    assert "deduplikator" in msgs[0].lower()
    assert reverse("deduplikator_zrodel:duplicate_sources") in msgs[0]


@pytest.mark.django_db
def test_ostrzez_o_zduplikowanych_zrodlach_milczy_bez_duplikatow():
    baker.make(Zrodlo, nazwa="Zupełnie Unikalne Czasopismo")
    wynik = Komparator.porownaj_container_title("Zupełnie Unikalne Czasopismo")

    request = _request_z_messages()
    ostrzez_o_zduplikowanych_zrodlach(request, wynik)

    assert list(request._messages) == []


@pytest.mark.django_db
def test_reprezentant_duplikatow_to_zrodlo_z_publikacjami():
    # Reprezentantem ma być rekord realnie używany (z publikacjami),
    # nie ten o najniższym pk, gdy ten pierwszy jest pustym duplikatem.
    pusty = baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")
    aktywny = baker.make(Zrodlo, nazwa="Zeszyty Naukowe SGSP")
    assert pusty.pk < aktywny.pk  # aktywny ma WYŻSZE pk
    baker.make(Wydawnictwo_Ciagle, zrodlo=aktywny)

    wynik = Komparator.porownaj_container_title("Zeszyty Naukowe SGSP")

    # Mimo wyższego pk wybrany ma być rekord z publikacją.
    assert wynik.rekord_po_stronie_bpp == aktywny
