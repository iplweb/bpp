from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from zglos_publikacje.forms import (
    STRONA_WWW_HELP_TEXT,
    Zgloszenie_Publikacji_DaneForm,
)
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
@pytest.mark.parametrize("forma_dostepu", ["OTWARTY", "OGRANICZONY"])
def test_strona_www_opcjonalna_dla_pozostalych(forma_dostepu):
    """Dla „Inne" (np. materiały konferencyjne) pole nie jest wymagane —
    PBN nie wymaga linku, bo te publikacje nie są wysyłane do PBN."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(
        rodzaj="POZOSTALE", forma_dostepu=forma_dostepu
    )
    assert form.fields["strona_www"].required is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rodzaj,forma_dostepu",
    [
        ("ARTYKUL", "OTWARTY"),
        ("ARTYKUL", "OGRANICZONY"),
        ("MONOGRAFIA", "OTWARTY"),
        ("MONOGRAFIA", "OGRANICZONY"),
        ("ROZDZIAL", "OTWARTY"),
        ("ROZDZIAL", "OGRANICZONY"),
        ("POZOSTALE", "OTWARTY"),
        ("POZOSTALE", "OGRANICZONY"),
    ],
)
def test_help_text_strona_www_zalezny_od_kombinacji(rodzaj, forma_dostepu):
    """Dla każdej kombinacji (rodzaj, forma_dostepu) help_text jest dobrany
    z tablicy STRONA_WWW_HELP_TEXT i pasuje do ustawień (np. brak prefiksu
    „Pole wymagane — PBN" dla „Inne", obecny dla pozostałych rodzajów)."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(rodzaj=rodzaj, forma_dostepu=forma_dostepu)
    expected = STRONA_WWW_HELP_TEXT[(rodzaj, forma_dostepu)]
    assert form.fields["strona_www"].help_text == expected
    if rodzaj == "POZOSTALE":
        assert "PBN" not in expected
        assert "Pole wymagane" not in expected
        if forma_dostepu == "OTWARTY":
            assert expected == ""
    else:
        assert expected.startswith("Pole wymagane")


@pytest.mark.django_db
def test_help_text_artykul_otwarty_bez_katalogow_bn_nukat():
    """Dla artykułu w otwartym dostępie comment nie ma fragmentu o BN/NUKAT
    — to dotyczy tylko monografii/rozdziału w dostępie ograniczonym."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(rodzaj="ARTYKUL", forma_dostepu="OTWARTY")
    h = form.fields["strona_www"].help_text
    assert "Biblioteki Narodowej" not in h
    assert "NUKAT" not in h
    assert "Dla publikacji w otwartym dostępie" in h


@pytest.mark.django_db
def test_help_text_artykul_ograniczony_bez_katalogow_bn_nukat():
    """Dla artykułu w dostępie ograniczonym też nie ma fragmentu o BN/NUKAT
    — pojawia się on dopiero przy monografiach i rozdziałach."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(rodzaj="ARTYKUL", forma_dostepu="OGRANICZONY")
    h = form.fields["strona_www"].help_text
    assert "Biblioteki Narodowej" not in h
    assert "NUKAT" not in h
    assert "linku do strony z informacją o publikacji" in h


@pytest.mark.django_db
@pytest.mark.parametrize("rodzaj", ["MONOGRAFIA", "ROZDZIAL"])
def test_help_text_monografia_rozdzial_ograniczony_z_katalogami(rodzaj):
    """Dla monografii i rozdziału w dostępie ograniczonym pojawia się
    fragment o linku do katalogów BN/NUKAT."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(rodzaj=rodzaj, forma_dostepu="OGRANICZONY")
    h = form.fields["strona_www"].help_text
    assert "Biblioteki Narodowej" in h
    assert "NUKAT" in h


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


@pytest.mark.django_db
def test_walidacja_plikow_dla_dostepu_ograniczonego_z_dict():
    """Test reprodukuje błąd AttributeError: 'dict' object has no attribute 'getlist'.

    W wizardie, gdy formularz jest walidowany ponownie w render_done(),
    self.files może być zwykłym dict, a nie QueryDict.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    baker.make(Uczelnia)

    # Najpierw sprawdźmy czy formularz bez błędów w polach dochodzi do clean()
    form = Zgloszenie_Publikacji_DaneForm(
        data={
            "tytul_oryginalny": "Test",
            "rok": 2024,
            "email": "test@example.com",
            "strona_www": "https://example.com/test",
            "zgoda_na_publikacje_pelnego_tekstu": "True",
        },
        files={},  # Pusty dict - to powinno wywołać błąd o braku plików
        rodzaj="ARTYKUL",
        forma_dostepu="OGRANICZONY",
    )

    # Formularz powinien być invalid, ale bez AttributeError
    is_valid = form.is_valid()
    assert is_valid is False

    # Błąd powinien dotyczyć braku pliku, nie getlist()
    errors = form.errors.get("__all__", [])
    assert any("plik" in str(e).lower() for e in errors), (
        f"Oczekiwany błąd o braku pliku, otrzymano: {errors}"
    )
