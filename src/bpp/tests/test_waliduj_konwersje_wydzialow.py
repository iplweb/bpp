from io import StringIO

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models import Jednostka, Wydzial


@pytest.mark.django_db
def test_wykrywa_kolizje_nazwy():
    baker.make(Wydzial, nazwa="Kolizja", skrot="K1")
    baker.make(Jednostka, nazwa="Kolizja")
    out = StringIO()
    call_command("waliduj_konwersje_wydzialow", stdout=out)
    assert "Kolizja" in out.getvalue()


@pytest.mark.django_db
def test_czysto_gdy_brak_problemow():
    baker.make(Wydzial, nazwa="Wydzial A", skrot="WA")
    out = StringIO()
    call_command("waliduj_konwersje_wydzialow", stdout=out)
    assert "0 problem" in out.getvalue().lower() or "brak" in out.getvalue().lower()


@pytest.mark.django_db
def test_wykrywa_kolizje_pbn_id():
    baker.make(Wydzial, nazwa="Wydzial PBN", skrot="WPBN", pbn_id=12345)
    baker.make(Jednostka, nazwa="Inna nazwa", skrot="INNA", pbn_id=12345)
    out = StringIO()
    call_command("waliduj_konwersje_wydzialow", stdout=out)
    assert "pbn_id" in out.getvalue().lower()
    assert "12345" in out.getvalue()


@pytest.mark.django_db
def test_po_konwersji_ponowne_uruchomienie_nie_zglasza_falszywych_kolizji():
    baker.make(
        Wydzial,
        nazwa="Wydzial Konwertowany",
        skrot="WK",
        skrot_nazwy="WYDZ-K",
        pbn_id=54321,
    )
    call_command("konwertuj_wydzialy_na_jednostki")

    out = StringIO()
    call_command("waliduj_konwersje_wydzialow", stdout=out)
    output = out.getvalue()
    assert "KOLIZJA" not in output
    assert "0 problem" in output.lower() or "brak" in output.lower()
