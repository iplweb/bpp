import pytest
from model_bakery import baker

from bpp.models import Zrodlo
from przemapuj_zrodla_pbn.forms import PrzeMapowanieZrodlaForm


@pytest.mark.django_db
def test_przemapowanie_zrodla_form_initialization():
    """Test czy formularz inicjalizuje się poprawnie"""
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    # Pusty queryset
    sugerowane_queryset = Zrodlo.objects.none()

    form = PrzeMapowanieZrodlaForm(
        zrodlo_skasowane=zrodlo_skasowane, sugerowane_zrodla=sugerowane_queryset
    )

    assert "zrodlo_docelowe" in form.fields
    # Pole nie jest wymagane na poziomie pola, walidacja jest w clean()


@pytest.mark.django_db
def test_przemapowanie_zrodla_form_with_suggested_sources():
    """Test czy formularz poprawnie ustawia queryset z sugerowanych źródeł"""
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    journal_active = baker.make(
        "pbn_api.Journal", status="ACTIVE", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo_sugerowane = baker.make("bpp.Zrodlo", pbn_uid=journal_active)

    # Queryset z sugerowanym źródłem
    sugerowane_queryset = Zrodlo.objects.filter(pk=zrodlo_sugerowane.pk)

    form = PrzeMapowanieZrodlaForm(
        zrodlo_skasowane=zrodlo_skasowane, sugerowane_zrodla=sugerowane_queryset
    )

    # Sprawdź czy queryset zawiera sugerowane źródło
    queryset = form.fields["zrodlo_docelowe"].queryset
    assert zrodlo_sugerowane in queryset


@pytest.mark.django_db
def test_przemapowanie_zrodla_form_valid_data():
    """Test czy formularz akceptuje poprawne dane"""
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    journal_active = baker.make(
        "pbn_api.Journal", status="ACTIVE", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo_docelowe = baker.make("bpp.Zrodlo", pbn_uid=journal_active)

    # Queryset z docelowym źródłem
    sugerowane_queryset = Zrodlo.objects.filter(pk=zrodlo_docelowe.pk)

    form = PrzeMapowanieZrodlaForm(
        data={"typ_wyboru": "zrodlo", "zrodlo_docelowe": zrodlo_docelowe.pk},
        zrodlo_skasowane=zrodlo_skasowane,
        sugerowane_zrodla=sugerowane_queryset,
    )

    assert form.is_valid()
    assert form.cleaned_data["zrodlo_docelowe"] == zrodlo_docelowe


@pytest.mark.django_db
def test_przemapowanie_zrodla_form_invalid_empty_data():
    """Test czy formularz odrzuca puste dane - brak wybranego źródła"""
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    # Pusty queryset
    sugerowane_queryset = Zrodlo.objects.none()

    form = PrzeMapowanieZrodlaForm(
        data={"typ_wyboru": "zrodlo"},  # Typ wybrany, ale brak zrodlo_docelowe
        zrodlo_skasowane=zrodlo_skasowane,
        sugerowane_zrodla=sugerowane_queryset,
    )

    assert not form.is_valid()
    # Błąd powinien być w __all__ bo walidacja jest w clean()
    assert "__all__" in form.errors
    assert "Wybierz źródło docelowe z BPP" in form.errors["__all__"]
