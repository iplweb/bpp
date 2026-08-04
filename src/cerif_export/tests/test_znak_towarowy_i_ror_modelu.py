"""Znak towarowy poza eksportem + walidacja ROR na poziomie modelu."""

import pytest
from django.core.exceptions import ValidationError
from model_bakery import baker

from bpp.models import Jednostka, Patent, Rodzaj_Prawa_Patentowego, Uczelnia
from cerif_export import const
from cerif_export.providers import provider_dla_setu


@pytest.mark.django_db
def test_znak_towarowy_nie_wychodzi_w_eksporcie(
    uczelnia, jednostka, fabryka_autorow, status_ok
):
    """``Patent/Type`` jest obowiązkowy i ograniczony do gałęzi „patent".

    Samo pominięcie mapowania dawało fallback ``c_15cd patent``, czyli
    deklarowanie znaku towarowego patentem. Dlatego takie rekordy nie
    wychodzą wcale.
    """
    # `nazwa` jest unikalna, a oba wiersze są w baseline — więc
    # update_or_create, nie baker.make.
    wynalazek, _ = Rodzaj_Prawa_Patentowego.objects.update_or_create(
        nazwa="wynalazek", defaults={"eksportuj_jako_patent": True}
    )
    znak, _ = Rodzaj_Prawa_Patentowego.objects.update_or_create(
        nazwa="znak towarowy", defaults={"eksportuj_jako_patent": False}
    )

    autor = fabryka_autorow("Wynalazca")
    prawdziwy = baker.make(
        Patent,
        tytul_oryginalny="Wynalazek",
        rodzaj_prawa=wynalazek,
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )
    prawdziwy.dodaj_autora(autor, jednostka)

    towarowy = baker.make(
        Patent,
        tytul_oryginalny="Logo",
        rodzaj_prawa=znak,
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )
    towarowy.dodaj_autora(autor, jednostka)

    obiekty, _ = provider_dla_setu(const.SET_PATENTS).strona(uczelnia, rozmiar=100)
    pki = {o.pk for o in obiekty}

    assert prawdziwy.pk in pki
    assert towarowy.pk not in pki


@pytest.mark.django_db
def test_patent_bez_rodzaju_prawa_nadal_wychodzi(
    uczelnia, jednostka, fabryka_autorow, status_ok
):
    """``rodzaj_prawa=NULL`` to prawdziwy patent bez doprecyzowania,
    a nie inne prawo własności przemysłowej."""
    patent = baker.make(
        Patent,
        tytul_oryginalny="Bez rodzaju",
        rodzaj_prawa=None,
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )
    patent.dodaj_autora(fabryka_autorow("Autor"), jednostka)

    obiekty, _ = provider_dla_setu(const.SET_PATENTS).strona(uczelnia, rozmiar=100)

    assert patent.pk in {o.pk for o in obiekty}


# -- walidacja ROR na modelu ---------------------------------------------


@pytest.mark.django_db
def test_full_clean_odrzuca_bledny_ror_uczelni(uczelnia):
    """Walidacja musi działać poza adminem — import XLSX, loaddata, shell."""
    uczelnia.ror_id = "https://ror.org/0111ttp83"  # zła suma kontrolna

    with pytest.raises(ValidationError) as wyjatek:
        uczelnia.full_clean()

    assert "ror_id" in wyjatek.value.error_dict


@pytest.mark.django_db
def test_full_clean_odrzuca_bledny_ror_jednostki(uczelnia):
    jednostka = Jednostka(
        nazwa="Katedra", skrot="KAT", uczelnia=uczelnia, ror_id="https://ror.org/zzz"
    )

    with pytest.raises(ValidationError) as wyjatek:
        jednostka.full_clean()

    assert "ror_id" in wyjatek.value.error_dict


@pytest.mark.django_db
def test_full_clean_przepuszcza_poprawny_i_pusty_ror(uczelnia):
    uczelnia.ror_id = "https://ror.org/016f61126"
    uczelnia.full_clean()

    uczelnia.ror_id = ""
    uczelnia.full_clean()


def test_uczelnia_ma_walidator_na_polu():
    """Regresja: bez ``validators=[...]`` walidacja żyłaby tylko w adminie."""
    from bpp.util.ror import waliduj

    assert waliduj in Uczelnia._meta.get_field("ror_id").validators
    assert waliduj in Jednostka._meta.get_field("ror_id").validators
