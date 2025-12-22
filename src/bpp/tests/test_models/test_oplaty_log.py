"""Tests for OplatyPublikacjiLog model and log_oplaty_change helper."""

from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import OplatyPublikacjiLog, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.models.oplaty_log import log_oplaty_change


@pytest.mark.django_db
def test_oplaty_publikacji_log_create():
    """Test creating OplatyPublikacjiLog entry directly."""
    pub = baker.make(Wydawnictwo_Ciagle, rok=2024)
    ct = ContentType.objects.get_for_model(pub)

    log_entry = OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub.pk,
        changed_by="test_command",
        prev_opl_pub_cost_free=None,
        new_opl_pub_cost_free=True,
    )

    assert log_entry.pk is not None
    assert log_entry.publikacja == pub
    assert log_entry.changed_by == "test_command"
    assert log_entry.prev_opl_pub_cost_free is None
    assert log_entry.new_opl_pub_cost_free is True


@pytest.mark.django_db
def test_log_oplaty_change_helper():
    """Test log_oplaty_change helper function."""
    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2024,
        opl_pub_cost_free=None,
        opl_pub_research_potential=False,
        opl_pub_research_or_development_projects=None,
        opl_pub_other=None,
        opl_pub_amount=None,
    )

    log_oplaty_change(
        pub,
        changed_by="import_test",
        new_opl_pub_cost_free=True,
    )

    log_entry = OplatyPublikacjiLog.objects.get(object_id=pub.pk)
    assert log_entry.changed_by == "import_test"
    assert log_entry.prev_opl_pub_cost_free is None
    assert log_entry.prev_opl_pub_research_potential is False
    assert log_entry.new_opl_pub_cost_free is True


@pytest.mark.django_db
def test_log_oplaty_change_with_source_file():
    """Test log_oplaty_change with source file info."""
    pub = baker.make(Wydawnictwo_Zwarte, rok=2024)

    log_oplaty_change(
        pub,
        changed_by="import_oplaty_publikacje",
        source_file="test_file.xlsx",
        source_row=42,
        new_opl_pub_cost_free=False,
        new_opl_pub_amount=Decimal("1500.00"),
    )

    log_entry = OplatyPublikacjiLog.objects.get(object_id=pub.pk)
    assert log_entry.source_file == "test_file.xlsx"
    assert log_entry.source_row == 42
    assert log_entry.new_opl_pub_cost_free is False
    assert log_entry.new_opl_pub_amount == Decimal("1500.00")


@pytest.mark.django_db
def test_log_oplaty_change_preserves_previous_values():
    """Test that log_oplaty_change preserves previous values."""
    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2024,
        opl_pub_cost_free=False,
        opl_pub_research_potential=True,
        opl_pub_research_or_development_projects=False,
        opl_pub_other=True,
        opl_pub_amount=Decimal("2500.50"),
    )

    log_oplaty_change(
        pub,
        changed_by="update_test",
        new_opl_pub_cost_free=True,
        new_opl_pub_research_potential=False,
        new_opl_pub_research_or_development_projects=False,
        new_opl_pub_other=False,
        new_opl_pub_amount=None,
    )

    log_entry = OplatyPublikacjiLog.objects.get(object_id=pub.pk)

    # Check previous values
    assert log_entry.prev_opl_pub_cost_free is False
    assert log_entry.prev_opl_pub_research_potential is True
    assert log_entry.prev_opl_pub_research_or_development_projects is False
    assert log_entry.prev_opl_pub_other is True
    assert log_entry.prev_opl_pub_amount == Decimal("2500.50")

    # Check new values
    assert log_entry.new_opl_pub_cost_free is True
    assert log_entry.new_opl_pub_research_potential is False
    assert log_entry.new_opl_pub_research_or_development_projects is False
    assert log_entry.new_opl_pub_other is False
    assert log_entry.new_opl_pub_amount is None


@pytest.mark.django_db
def test_oplaty_publikacji_log_str():
    """Test OplatyPublikacjiLog __str__ method."""
    pub = baker.make(Wydawnictwo_Ciagle, rok=2024, tytul_oryginalny="Test Publication")
    ct = ContentType.objects.get_for_model(pub)

    log_entry = OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=pub.pk,
        changed_by="test",
    )

    str_repr = str(log_entry)
    assert "test" in str_repr
    assert log_entry.changed_at.strftime("%Y") in str_repr


@pytest.mark.django_db
def test_oplaty_publikacji_log_ordering():
    """Test that logs are ordered by changed_at descending."""
    pub = baker.make(Wydawnictwo_Ciagle, rok=2024)
    ct = ContentType.objects.get_for_model(pub)

    # Create multiple log entries
    for i in range(3):
        OplatyPublikacjiLog.objects.create(
            content_type=ct,
            object_id=pub.pk,
            changed_by=f"test_{i}",
        )

    logs = list(OplatyPublikacjiLog.objects.all())

    # Most recent should be first
    assert logs[0].changed_by == "test_2"
    assert logs[2].changed_by == "test_0"


@pytest.mark.django_db
def test_log_works_with_wydawnictwo_zwarte():
    """Test that logging works with Wydawnictwo_Zwarte."""
    pub = baker.make(Wydawnictwo_Zwarte, rok=2024)

    log_oplaty_change(
        pub,
        changed_by="test_zwarte",
        new_opl_pub_cost_free=True,
    )

    log_entry = OplatyPublikacjiLog.objects.get(object_id=pub.pk)
    assert log_entry.publikacja == pub
    assert log_entry.content_type.model == "wydawnictwo_zwarte"
