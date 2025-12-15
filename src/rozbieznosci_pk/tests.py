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
