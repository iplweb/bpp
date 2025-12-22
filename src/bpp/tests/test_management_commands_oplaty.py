"""Tests for oplaty-related management commands."""

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models import OplatyPublikacjiLog, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


@pytest.fixture
def pbn_publication():
    """Create a PBN Publication for linking."""
    from pbn_api.models import Publication

    return baker.make(Publication)


@pytest.fixture
def wydawnictwo_ciagle_with_pbn_uid(pbn_publication):
    """Create Wydawnictwo_Ciagle with PBN UID but no fee data."""
    return baker.make(
        Wydawnictwo_Ciagle,
        rok=2024,
        pbn_uid=pbn_publication,
        opl_pub_cost_free=None,
        opl_pub_research_potential=None,
        opl_pub_research_or_development_projects=None,
        opl_pub_other=None,
        opl_pub_amount=None,
    )


@pytest.fixture
def wydawnictwo_zwarte_with_pbn_uid():
    """Create Wydawnictwo_Zwarte with PBN UID but no fee data."""
    from pbn_api.models import Publication

    pub = baker.make(Publication)
    return baker.make(
        Wydawnictwo_Zwarte,
        rok=2024,
        pbn_uid=pub,
        opl_pub_cost_free=None,
        opl_pub_research_potential=None,
        opl_pub_research_or_development_projects=None,
        opl_pub_other=None,
        opl_pub_amount=None,
    )


@pytest.mark.django_db
def test_ustaw_bezkosztowe_sets_cost_free(wydawnictwo_ciagle_with_pbn_uid):
    """Test that command sets opl_pub_cost_free=True for publications without fee data."""
    pub = wydawnictwo_ciagle_with_pbn_uid
    assert pub.opl_pub_cost_free is None

    call_command("import_oplaty_publikacje_ustaw_bezkosztowe", rok=2024)

    pub.refresh_from_db()
    assert pub.opl_pub_cost_free is True


@pytest.mark.django_db
def test_ustaw_bezkosztowe_creates_log_entry(wydawnictwo_ciagle_with_pbn_uid):
    """Test that command creates a log entry."""
    pub = wydawnictwo_ciagle_with_pbn_uid

    call_command("import_oplaty_publikacje_ustaw_bezkosztowe", rok=2024)

    log_entry = OplatyPublikacjiLog.objects.get(object_id=pub.pk)
    assert log_entry.changed_by == "import_oplaty_publikacje_ustaw_bezkosztowe"
    assert log_entry.prev_opl_pub_cost_free is None
    assert log_entry.new_opl_pub_cost_free is True
    assert log_entry.rok == 2024


@pytest.mark.django_db
def test_ustaw_bezkosztowe_skips_publications_with_fee_data():
    """Test that command skips publications that already have fee data."""
    from pbn_api.models import Publication

    pbn_pub = baker.make(Publication)
    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2024,
        pbn_uid=pbn_pub,
        opl_pub_cost_free=False,  # Already has fee data
    )

    call_command("import_oplaty_publikacje_ustaw_bezkosztowe", rok=2024)

    pub.refresh_from_db()
    assert pub.opl_pub_cost_free is False  # Unchanged
    assert not OplatyPublikacjiLog.objects.filter(object_id=pub.pk).exists()


@pytest.mark.django_db
def test_ustaw_bezkosztowe_skips_publications_without_pbn_uid():
    """Test that command skips publications without PBN UID."""
    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2024,
        pbn_uid=None,
        opl_pub_cost_free=None,
    )

    call_command("import_oplaty_publikacje_ustaw_bezkosztowe", rok=2024)

    pub.refresh_from_db()
    assert pub.opl_pub_cost_free is None  # Unchanged
    assert not OplatyPublikacjiLog.objects.filter(object_id=pub.pk).exists()


@pytest.mark.django_db
def test_ustaw_bezkosztowe_filters_by_year():
    """Test that command only processes publications from the specified year."""
    from pbn_api.models import Publication

    pbn_pub_2024 = baker.make(Publication)
    pbn_pub_2023 = baker.make(Publication)

    pub_2024 = baker.make(
        Wydawnictwo_Ciagle,
        rok=2024,
        pbn_uid=pbn_pub_2024,
        opl_pub_cost_free=None,
    )
    pub_2023 = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        pbn_uid=pbn_pub_2023,
        opl_pub_cost_free=None,
    )

    call_command("import_oplaty_publikacje_ustaw_bezkosztowe", rok=2024)

    pub_2024.refresh_from_db()
    pub_2023.refresh_from_db()

    assert pub_2024.opl_pub_cost_free is True
    assert pub_2023.opl_pub_cost_free is None  # Not processed


@pytest.mark.django_db
def test_ustaw_bezkosztowe_processes_both_models(
    wydawnictwo_ciagle_with_pbn_uid, wydawnictwo_zwarte_with_pbn_uid
):
    """Test that command processes both Wydawnictwo_Ciagle and Wydawnictwo_Zwarte."""
    call_command("import_oplaty_publikacje_ustaw_bezkosztowe", rok=2024)

    wydawnictwo_ciagle_with_pbn_uid.refresh_from_db()
    wydawnictwo_zwarte_with_pbn_uid.refresh_from_db()

    assert wydawnictwo_ciagle_with_pbn_uid.opl_pub_cost_free is True
    assert wydawnictwo_zwarte_with_pbn_uid.opl_pub_cost_free is True


@pytest.mark.django_db
def test_ustaw_bezkosztowe_dry_run_does_not_save(wydawnictwo_ciagle_with_pbn_uid):
    """Test that --dry flag prevents changes from being saved."""
    pub = wydawnictwo_ciagle_with_pbn_uid

    call_command("import_oplaty_publikacje_ustaw_bezkosztowe", rok=2024, dry=True)

    pub.refresh_from_db()
    assert pub.opl_pub_cost_free is None  # Should remain unchanged
    assert not OplatyPublikacjiLog.objects.filter(object_id=pub.pk).exists()
