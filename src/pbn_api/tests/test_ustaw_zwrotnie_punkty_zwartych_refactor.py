from decimal import Decimal

import pytest
from model_bakery import baker

from bpp import const


@pytest.fixture
def wydawca_poziom_II(db):
    from bpp.models.wydawca import Poziom_Wydawcy, Wydawca

    w = baker.make(Wydawca)
    baker.make(Poziom_Wydawcy, wydawca=w, rok=2023, poziom=2)
    return w


def _zwarte_ksiazka_autorska(wydawca):
    from bpp.models import Charakter_Formalny, Wydawnictwo_Zwarte

    cf = Charakter_Formalny.objects.filter(
        charakter_sloty=const.CHARAKTER_SLOTY_KSIAZKA
    ).first()
    rekord = baker.make(
        Wydawnictwo_Zwarte,
        wydawca=wydawca,
        rok=2023,
        charakter_formalny=cf,
        punkty_kbn=Decimal(0),
    )
    rekord.dodaj_autora(
        autor=baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan"),
        jednostka=baker.make("bpp.Jednostka"),
        zapisany_jako="Kowalski Jan",
        typ_odpowiedzialnosci_skrot="aut.",
    )
    return rekord


@pytest.mark.django_db
def test_komenda_ustawia_200_dla_monografii_poziom_II(
    wydawca_poziom_II, typy_odpowiedzialnosci, charaktery_formalne
):
    from django.core.management import call_command

    rekord = _zwarte_ksiazka_autorska(wydawca_poziom_II)
    call_command("ustaw_zwrotnie_punkty_zwartych", min_rok=2023)
    rekord.refresh_from_db()
    assert rekord.punkty_kbn == Decimal(200)
