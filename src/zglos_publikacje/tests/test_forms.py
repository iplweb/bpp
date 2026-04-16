from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from zglos_publikacje.forms import Zgloszenie_Publikacji_DaneForm
from zglos_publikacje.views import Zgloszenie_PublikacjiWizard


@pytest.mark.django_db
def test_strona_www_wymagana_dla_otwarty_dostepu():
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(rodzaj="ARTYKUL", forma_dostepu="OTWARTY")
    assert form.fields["strona_www"].required is True


@pytest.mark.django_db
def test_strona_www_wymagana_dla_ograniczonego_dostepu():
    """Pole link wymagane zawsze — PBN tego wymaga niezależnie od trybu OA."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(rodzaj="ARTYKUL", forma_dostepu="OGRANICZONY")
    assert form.fields["strona_www"].required is True


@pytest.mark.django_db
def test_brak_pol_wydawcy_dla_monografii():
    """Pola wydawca i wydawca_zgloszenia usunięte z formularza użytkownika."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(
        rodzaj="MONOGRAFIA", forma_dostepu="OGRANICZONY"
    )
    assert "wydawca" not in form.fields
    assert "wydawca_zgloszenia" not in form.fields


@pytest.mark.django_db
def test_brak_pol_wydawcy_dla_rozdzialu():
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(
        rodzaj="ROZDZIAL", forma_dostepu="OGRANICZONY"
    )
    assert "wydawca" not in form.fields
    assert "wydawca_zgloszenia" not in form.fields


@pytest.mark.django_db
def test_wydawnictwo_nadrzedne_widoczne_dla_rozdzialu():
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(
        rodzaj="ROZDZIAL", forma_dostepu="OGRANICZONY"
    )
    assert "wydawnictwo_nadrzedne" in form.fields
    assert "wydawnictwo_nadrzedne_tekst" in form.fields


@pytest.mark.django_db
def test_brak_wydawnictwa_nadrzednego_dla_monografii():
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(
        rodzaj="MONOGRAFIA", forma_dostepu="OGRANICZONY"
    )
    assert "wydawnictwo_nadrzedne" not in form.fields
    assert "wydawnictwo_nadrzedne_tekst" not in form.fields


def test_set_wydawca_nie_resetuje_gdy_brak_pol_w_dane():
    """_set_wydawca zwraca wcześnie, jeśli pola wydawcy nie ma w danych formularza.

    Chroni przed wyczyszczeniem wydawcy ustawionego ręcznie przez bibliotekarza.
    """
    wizard = Zgloszenie_PublikacjiWizard.__new__(Zgloszenie_PublikacjiWizard)
    wizard.object = MagicMock()
    wizard.object.wydawca_bpp = "sentinel_bpp"
    wizard.object.wydawca_pbn = "sentinel_pbn"
    wizard.object.wydawca_zgloszenia = "sentinel_tekst"

    wizard._set_wydawca({})

    assert wizard.object.wydawca_bpp == "sentinel_bpp"
    assert wizard.object.wydawca_pbn == "sentinel_pbn"
    assert wizard.object.wydawca_zgloszenia == "sentinel_tekst"
