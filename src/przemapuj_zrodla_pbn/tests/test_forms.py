import pytest
from model_bakery import baker

from bpp.models import Zrodlo
from przemapuj_zrodla_pbn.forms import PrzeMapowanieZrodlaForm


@pytest.mark.django_db
def test_przemapowanie_zrodla_form_initialization():
    """Test czy formularz inicjalizuje się poprawnie"""
    journal_deleted = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    # Pusty queryset
    sugerowane_queryset = Zrodlo.objects.none()

    form = PrzeMapowanieZrodlaForm(
        zrodlo_skasowane=zrodlo_skasowane, sugerowane_zrodla=sugerowane_queryset
    )

    assert "zrodlo_docelowe" in form.fields
    assert form.fields["zrodlo_docelowe"].required is True


@pytest.mark.django_db
def test_przemapowanie_zrodla_form_with_suggested_sources():
    """Test czy formularz poprawnie ustawia queryset z sugerowanych źródeł"""
    journal_deleted = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    journal_active = baker.make("pbn_api.Journal", status="ACTIVE")
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
    journal_deleted = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    journal_active = baker.make("pbn_api.Journal", status="ACTIVE")
    zrodlo_docelowe = baker.make("bpp.Zrodlo", pbn_uid=journal_active)

    # Queryset z docelowym źródłem
    sugerowane_queryset = Zrodlo.objects.filter(pk=zrodlo_docelowe.pk)

    form = PrzeMapowanieZrodlaForm(
        data={"zrodlo_docelowe": zrodlo_docelowe.pk},
        zrodlo_skasowane=zrodlo_skasowane,
        sugerowane_zrodla=sugerowane_queryset,
    )

    assert form.is_valid()
    assert form.cleaned_data["zrodlo_docelowe"] == zrodlo_docelowe


@pytest.mark.django_db
def test_przemapowanie_zrodla_form_invalid_empty_data():
    """Test czy formularz odrzuca puste dane"""
    journal_deleted = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo_skasowane = baker.make("bpp.Zrodlo", pbn_uid=journal_deleted)

    # Pusty queryset
    sugerowane_queryset = Zrodlo.objects.none()

    form = PrzeMapowanieZrodlaForm(
        data={},
        zrodlo_skasowane=zrodlo_skasowane,
        sugerowane_zrodla=sugerowane_queryset,
    )

    assert not form.is_valid()
    assert "zrodlo_docelowe" in form.errors
