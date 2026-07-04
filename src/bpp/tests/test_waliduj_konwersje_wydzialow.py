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
