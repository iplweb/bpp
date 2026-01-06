"""Tests for rozbieznosci_pk cache recalculation functionality."""

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Wydawnictwo_Ciagle,
    Zrodlo,
)
from rozbieznosci_if.views import ustaw_pole_ze_zrodla
from rozbieznosci_pk.models import RozbieznosciPkLog


def get_cache_rekord_id(wc):
    """Get the rekord_id tuple for Cache_Punktacja_Autora lookup."""
    ctype = ContentType.objects.get_for_model(Wydawnictwo_Ciagle).pk
    return [ctype, wc.pk]


@pytest.fixture
def wydawnictwo_z_autorem_i_dyscyplina(
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    typy_odpowiedzialnosci,
    rodzaj_autora_n,
    rok,
):
    """Create a Wydawnictwo_Ciagle with an author assigned to a discipline."""
    # Assign author to discipline for this year (with rodzaj_autora for slot calculation)
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Add author to publication with discipline pinned
    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    # Set initial punkty_kbn (needs to be > 0 for slot calculation)
    wydawnictwo_ciagle.punkty_kbn = 10
    wydawnictwo_ciagle.save()

    return wydawnictwo_ciagle


@pytest.fixture
def wydawnictwo_z_rozbieznoscia_pk(wydawnictwo_z_autorem_i_dyscyplina, rok):
    """Create a publication with punkty_kbn discrepancy from its source."""
    wc = wydawnictwo_z_autorem_i_dyscyplina

    # Create source with different punkty_kbn
    zrodlo = baker.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=rok, punkty_kbn=100)

    wc.zrodlo = zrodlo
    wc.punkty_kbn = 10  # Different from source's 100
    wc.save()

    return wc


@pytest.mark.django_db
def test_ustaw_pk_ze_zrodla_recalculates_cache(wydawnictwo_z_rozbieznoscia_pk):
    """Test that ustaw_pole_ze_zrodla recalculates Cache_Punktacja_Autora."""
    wc = wydawnictwo_z_rozbieznoscia_pk
    pk = wc.pk
    rekord_id = get_cache_rekord_id(wc)

    # Clear any existing cache entries
    Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id).delete()

    # Verify no cache exists initially
    assert not Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id).exists()

    # Call the function that updates punkty_kbn
    updated, errors = ustaw_pole_ze_zrodla(
        [pk],
        "punkty_kbn",
        RozbieznosciPkLog,
        "pk_before",
        "pk_after",
    )

    assert updated == 1
    assert errors == 0

    # Verify punkty_kbn was updated
    wc.refresh_from_db()
    assert wc.punkty_kbn == 100

    # Verify Cache_Punktacja_Autora was created/updated
    cache_entries = Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id)
    assert cache_entries.exists(), "Cache_Punktacja_Autora should be recalculated"


@pytest.mark.django_db
def test_task_ustaw_pk_ze_zrodla_recalculates_cache(wydawnictwo_z_rozbieznoscia_pk):
    """Test that Celery task recalculates Cache_Punktacja_Autora."""
    from rozbieznosci_pk.tasks import task_ustaw_pk_ze_zrodla

    wc = wydawnictwo_z_rozbieznoscia_pk
    pk = wc.pk
    rekord_id = get_cache_rekord_id(wc)

    # Clear any existing cache entries
    Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id).delete()

    # Verify no cache exists initially
    assert not Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id).exists()

    # Run the Celery task synchronously
    result = task_ustaw_pk_ze_zrodla.apply(args=([pk],)).result

    assert result["updated"] == 1
    assert result["errors"] == 0

    # Verify punkty_kbn was updated
    wc.refresh_from_db()
    assert wc.punkty_kbn == 100

    # Verify Cache_Punktacja_Autora was created/updated
    cache_entries = Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id)
    assert cache_entries.exists(), "Cache_Punktacja_Autora should be recalculated"


@pytest.mark.django_db
def test_task_ustaw_pk_ze_zrodla_creates_log(
    wydawnictwo_z_rozbieznoscia_pk, admin_user
):
    """Test that Celery task creates log entries with user."""
    from rozbieznosci_pk.tasks import task_ustaw_pk_ze_zrodla

    wc = wydawnictwo_z_rozbieznoscia_pk
    pk = wc.pk
    old_pk = wc.punkty_kbn

    # Run the Celery task synchronously with user_id
    task_ustaw_pk_ze_zrodla.apply(args=([pk],), kwargs={"user_id": admin_user.id})

    # Check log was created with correct user
    log = RozbieznosciPkLog.objects.filter(rekord_id=pk).first()
    assert log is not None
    assert log.pk_before == old_pk
    assert log.pk_after == 100
    assert log.user == admin_user


@pytest.mark.django_db
def test_task_ustaw_pk_ze_zrodla_nonexistent():
    """Test task handles nonexistent publication gracefully."""
    from rozbieznosci_pk.tasks import task_ustaw_pk_ze_zrodla

    # Run with nonexistent PK
    result = task_ustaw_pk_ze_zrodla.apply(args=([999999],)).result

    assert result["updated"] == 0
    assert result["errors"] == 1
    assert result["total"] == 1


@pytest.mark.django_db
def test_task_ustaw_pk_ze_zrodla_no_update_when_equal(rok):
    """Test task doesn't update when values are already equal."""
    from rozbieznosci_pk.tasks import task_ustaw_pk_ze_zrodla

    # Create publication with matching punkty_kbn
    zrodlo = baker.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=rok, punkty_kbn=50)

    wc = baker.make(Wydawnictwo_Ciagle, punkty_kbn=50, rok=rok, zrodlo=zrodlo)

    result = task_ustaw_pk_ze_zrodla.apply(args=([wc.pk],)).result

    assert result["updated"] == 0
    assert result["errors"] == 0

    # No log should be created
    assert not RozbieznosciPkLog.objects.filter(rekord_id=wc.pk).exists()


@pytest.mark.django_db
def test_task_ustaw_pk_ze_zrodla_invalid_user_id(wydawnictwo_z_rozbieznoscia_pk):
    """Test task handles invalid user_id gracefully."""
    from rozbieznosci_pk.tasks import task_ustaw_pk_ze_zrodla

    wc = wydawnictwo_z_rozbieznoscia_pk
    pk = wc.pk

    # Run with invalid user_id
    result = task_ustaw_pk_ze_zrodla.apply(
        args=([pk],), kwargs={"user_id": 999999}
    ).result

    assert result["updated"] == 1
    assert result["errors"] == 0

    # Log should exist but without user
    log = RozbieznosciPkLog.objects.filter(rekord_id=pk).first()
    assert log is not None
    assert log.user is None


@pytest.mark.django_db
def test_rozbieznosci_pk_log_str(wydawnictwo_z_rozbieznoscia_pk, admin_user):
    """Test RozbieznosciPkLog __str__ method."""
    wc = wydawnictwo_z_rozbieznoscia_pk

    log = RozbieznosciPkLog.objects.create(
        rekord=wc,
        zrodlo=wc.zrodlo,
        pk_before=10,
        pk_after=100,
        user=admin_user,
    )

    assert "10" in str(log)
    assert "100" in str(log)


@pytest.mark.django_db
def test_ignoruj_rozbieznosc_pk_str(wydawnictwo_z_rozbieznoscia_pk):
    """Test IgnorujRozbieznoscPk __str__ method."""
    from rozbieznosci_pk.models import IgnorujRozbieznoscPk

    ignore = IgnorujRozbieznoscPk.objects.create(object=wydawnictwo_z_rozbieznoscia_pk)

    assert "Ignoruj" in str(ignore)
    assert "MNiSW" in str(ignore)
