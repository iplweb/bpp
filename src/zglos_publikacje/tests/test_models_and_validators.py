
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from model_bakery import baker

from bpp.const import PUSTY_ADRES_EMAIL
from bpp.models import Uczelnia
from zglos_publikacje.models import (
    Obslugujacy_Zgloszenia_Wydzialow,
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Zalacznik,
)
from zglos_publikacje.validators import validate_file_extension_pdf


@pytest.mark.django_db
def test_zgloszenie_publikacji_moze_zostac_zwrocony_nowy():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, status=Zgloszenie_Publikacji.Statusy.NOWY
    )
    assert zgloszenie.moze_zostac_zwrocony() is True


@pytest.mark.django_db
def test_zgloszenie_publikacji_moze_zostac_zwrocony_po_zmianach():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, status=Zgloszenie_Publikacji.Statusy.PO_ZMIANACH
    )
    assert zgloszenie.moze_zostac_zwrocony() is True


@pytest.mark.django_db
def test_zgloszenie_publikacji_moze_zostac_zwrocony_zaakceptowany():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, status=Zgloszenie_Publikacji.Statusy.ZAAKCEPTOWANY
    )
    assert zgloszenie.moze_zostac_zwrocony() is False


@pytest.mark.django_db
def test_zgloszenie_publikacji_moze_zostac_zwrocony_wymaga_zmian():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, status=Zgloszenie_Publikacji.Statusy.WYMAGA_ZMIAN
    )
    assert zgloszenie.moze_zostac_zwrocony() is False


@pytest.mark.django_db
def test_zgloszenie_publikacji_moze_zostac_zwrocony_odrzucono():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, status=Zgloszenie_Publikacji.Statusy.ODRZUCONO
    )
    assert zgloszenie.moze_zostac_zwrocony() is False


@pytest.mark.django_db
def test_zgloszenie_publikacji_moze_zostac_zwrocony_spam():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, status=Zgloszenie_Publikacji.Statusy.SPAM
    )
    assert zgloszenie.moze_zostac_zwrocony() is False


@pytest.mark.django_db
def test_zgloszenie_publikacji_str_representation():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Test tytuł",
        email="test@example.com",
    )

    str_repr = str(zgloszenie)
    assert "Test tytuł" in str_repr
    assert "test@example.com" in str_repr


@pytest.mark.django_db
def test_zgloszenie_publikacji_default_values():
    zgloszenie = Zgloszenie_Publikacji()

    assert zgloszenie.status == Zgloszenie_Publikacji.Statusy.NOWY
    assert zgloszenie.zgoda_na_publikacje_pelnego_tekstu is False
    assert zgloszenie.przyczyna_zwrotu == ""


@pytest.mark.django_db
def test_validate_file_extension_pdf_valid():
    file_obj = SimpleUploadedFile(
        "test.pdf", b"file content", content_type="application/pdf"
    )
    validate_file_extension_pdf(file_obj)


@pytest.mark.django_db
def test_validate_file_extension_pdf_invalid():
    file_obj = SimpleUploadedFile(
        "test.txt", b"file content", content_type="text/plain"
    )

    with pytest.raises(ValidationError) as exc_info:
        validate_file_extension_pdf(file_obj)

    assert "Nieobsługiwany format pliku" in str(exc_info.value)


@pytest.mark.django_db
def test_validate_file_extension_pdf_uppercase():
    file_obj = SimpleUploadedFile(
        "test.PDF", b"file content", content_type="application/pdf"
    )
    validate_file_extension_pdf(file_obj)


@pytest.mark.django_db
def test_obsulgujacy_zgloszenia_wydzialow_multiple_same_email():
    uczelnia = baker.make(Uczelnia)
    # Faza B (#438) II-2: ``wydzial`` to FK->Jednostka (korzeń drzewa).
    wydzial = baker.make("bpp.Jednostka", uczelnia=uczelnia)

    user1 = baker.make("bpp.BppUser", email="test@example.com")
    user2 = baker.make("bpp.BppUser", email="test@example.com")

    Obslugujacy_Zgloszenia_Wydzialow.objects.create(user=user1, wydzial=wydzial)
    Obslugujacy_Zgloszenia_Wydzialow.objects.create(user=user2, wydzial=wydzial)

    result = Obslugujacy_Zgloszenia_Wydzialow.objects.emaile_dla_obslugujacego(wydzial)

    # Manager doesn't deduplicate by default
    assert len(result) == 2
    assert all(email == "test@example.com" for email in result)


@pytest.mark.django_db
def test_obsulgujacy_zgloszenia_wydzialow_empty_email():
    uczelnia = baker.make(Uczelnia)
    # Faza B (#438) II-2: ``wydzial`` to FK->Jednostka (korzeń drzewa).
    wydzial = baker.make("bpp.Jednostka", uczelnia=uczelnia)

    user = baker.make("bpp.BppUser", email=PUSTY_ADRES_EMAIL)

    Obslugujacy_Zgloszenia_Wydzialow.objects.create(user=user, wydzial=wydzial)

    result = Obslugujacy_Zgloszenia_Wydzialow.objects.emaile_dla_obslugujacego(wydzial)

    assert result is None


@pytest.mark.django_db
def test_obsulgujacy_zgloszenia_wydzialow_meta_unique():
    uczelnia = baker.make(Uczelnia)
    # Faza B (#438) II-2: ``wydzial`` to FK->Jednostka (korzeń drzewa).
    wydzial = baker.make("bpp.Jednostka", uczelnia=uczelnia)
    user = baker.make("bpp.BppUser")

    baker.make(
        Obslugujacy_Zgloszenia_Wydzialow, user=user, wydzial=wydzial
    )

    with pytest.raises(IntegrityError):
        baker.make(
            Obslugujacy_Zgloszenia_Wydzialow,
            user=user,
            wydzial=wydzial,
        )


@pytest.mark.django_db
def test_nowe_rodzaje_enum():
    """Nowe wartości Rodzaje są dostępne."""
    assert Zgloszenie_Publikacji.Rodzaje.ARTYKUL == 5
    assert Zgloszenie_Publikacji.Rodzaje.MONOGRAFIA == 4
    assert Zgloszenie_Publikacji.Rodzaje.INNE == 6
    # Legacy
    assert (
        Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
        == 1
    )


@pytest.mark.django_db
def test_formy_dostepu_enum():
    """FormyDostepu enum ma poprawne wartości."""
    assert (
        Zgloszenie_Publikacji.FormyDostepu.OTWARTY == 1
    )
    assert (
        Zgloszenie_Publikacji.FormyDostepu.OGRANICZONY == 2
    )


@pytest.mark.django_db
def test_zalacznik_tworzenie():
    """Zgloszenie_Publikacji_Zalacznik tworzy się."""
    zp = baker.make(Zgloszenie_Publikacji)
    zalacznik = Zgloszenie_Publikacji_Zalacznik.objects.create(
        zgloszenie=zp,
        oryginalna_nazwa_pliku="test.pdf",
        kolejnosc=0,
    )
    assert zalacznik.pk is not None
    assert zp.zalaczniki.count() == 1


@pytest.mark.django_db
def test_zalacznik_cascade_delete():
    """Usunięcie zgłoszenia kasuje załączniki."""
    zp = baker.make(Zgloszenie_Publikacji)
    Zgloszenie_Publikacji_Zalacznik.objects.create(
        zgloszenie=zp,
        oryginalna_nazwa_pliku="test.pdf",
    )
    zp_id = zp.pk
    zp.delete()
    assert not Zgloszenie_Publikacji_Zalacznik.objects.filter(
        zgloszenie_id=zp_id
    ).exists()


@pytest.mark.django_db
def test_uczelnia_wymagaj_oplatach_pola():
    """Nowe pola konfiguracji opłat na Uczelnia."""
    uczelnia = baker.make(Uczelnia)
    # Domyślne wartości
    assert uczelnia.wymagaj_oplatach_artykul is True
    assert uczelnia.wymagaj_oplatach_monografia is True
    assert uczelnia.wymagaj_oplatach_rozdzial is False
    assert uczelnia.wymagaj_oplatach_inne is False


@pytest.mark.django_db
def test_clean_wymaga_oplatach_konfigurowalnie():
    """Model.clean() respektuje konfigurowalne opłaty."""
    uczelnia = baker.make(Uczelnia)
    uczelnia.wymagaj_oplatach_artykul = False
    uczelnia.save()

    # Artykuł bez opłat powinien przejść walidację
    zp = baker.make(
        Zgloszenie_Publikacji,
        rodzaj_zglaszanej_publikacji=(
            Zgloszenie_Publikacji.Rodzaje.ARTYKUL
        ),
    )
    # Nie powinien rzucić wyjątku
    zp.clean()
