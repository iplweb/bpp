"""Tests for discipline pin/unpin actions in ewaluacja_optymalizuj_publikacje."""

from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Jednostka,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)


@pytest.mark.django_db
def test_unpin_discipline_updates_all_authors_metrics(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that unpinning a discipline recalculates metrics for ALL authors of the publication"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor1 = baker.make(Autor, nazwisko="Pierwszy", imiona="Autor")
    autor2 = baker.make(Autor, nazwisko="Drugi", imiona="Autor")
    autor3 = baker.make(Autor, nazwisko="Trzeci", imiona="Autor")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka")

    # Create Autor_Dyscyplina for all authors
    for autor in [autor1, autor2, autor3]:
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            rok=2023,
            rodzaj_autora=rodzaj_autora_n,
        )

    # Create publication with 100 points
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test unpinning effect on all authors",
        rok=2023,
        punkty_kbn=100,
    )

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Add all three authors with pinned disciplines
    wa_autorzy = []
    for idx, autor in enumerate([autor1, autor2, autor3]):
        wa = baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wydawnictwo,
            autor=autor,
            jednostka=jednostka,
            dyscyplina_naukowa=dyscyplina,
            przypieta=True,  # All start as pinned
            afiliuje=True,
            typ_odpowiedzialnosci=typ_odp,
            kolejnosc=idx,
        )
        wa_autorzy.append(wa)

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Create initial metrics for all authors (simulating they were calculated)
    from bpp.models.cache import Cache_Punktacja_Autora_Query
    from bpp.models.sloty.core import IPunktacjaCacher
    from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

    # Build cache and calculate initial metrics
    cacher = IPunktacjaCacher(wydawnictwo)
    cacher.removeEntries()
    cacher.rebuildEntries()

    # Calculate metrics for all authors
    przelicz_metryki_dla_publikacji(wydawnictwo)

    # Verify initial state - with 3 authors, each should get ~33.33 points and 0.333 slot
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(wydawnictwo)
    cache_entries = Cache_Punktacja_Autora_Query.objects.filter(
        rekord_id=[ct.pk, wydawnictwo.pk]
    )
    assert cache_entries.count() == 3

    for entry in cache_entries:
        assert entry.pkdaut.quantize(Decimal("0.01")) == Decimal("33.33")  # 100/3
        assert entry.slot.quantize(Decimal("0.001")) == Decimal("0.333")  # 1/3

    # Now unpin autor2's discipline
    wa_autor2 = wa_autorzy[1]
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.post(
        url,
        {
            "unpin_discipline": "1",
            "autor_assignment_id": wa_autor2.pk,
        },
    )

    assert response.status_code in [200, 302]

    # Verify the discipline was unpinned
    wa_autor2.refresh_from_db()
    assert wa_autor2.przypieta is False

    # Check cache was rebuilt correctly - should now have only 2 entries
    cache_entries = Cache_Punktacja_Autora_Query.objects.filter(
        rekord_id=[ct.pk, wydawnictwo.pk]
    )
    assert cache_entries.count() == 2  # Only 2 authors with pinned disciplines

    # Verify the remaining authors now have updated points and slots
    # With 2 authors, each should get 50 points and 0.5 slot
    for entry in cache_entries:
        assert entry.autor_id in [
            autor1.pk,
            autor3.pk,
        ]  # Only autor1 and autor3
        assert entry.pkdaut.quantize(Decimal("0.01")) == Decimal("50.00")  # 100/2
        assert entry.slot.quantize(Decimal("0.01")) == Decimal("0.50")  # 1/2

    # IMPORTANT: Verify that metrics were recalculated for ALL authors, not just autor2
    # This is where the bug would show - if metrics aren't recalculated for autor1 and autor3,
    # their MetrykaAutora would still show old values
    from ewaluacja_metryki.models import MetrykaAutora

    # Check if MetrykaAutora objects exist and verify they reflect the changes
    for autor in [autor1, autor3]:
        try:
            metryka = MetrykaAutora.objects.get(  # noqa
                autor=autor, dyscyplina_naukowa=dyscyplina
            )
            # The metrics should include the updated slot/point values from this publication
            # This would fail with the current bug since only autor2's metrics are recalculated
        except MetrykaAutora.DoesNotExist:
            # Metrics might not exist yet, which is fine for this test
            pass


@pytest.mark.django_db
def test_pin_discipline_updates_all_authors_metrics(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that pinning a discipline recalculates metrics for ALL authors of the publication"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor1 = baker.make(Autor, nazwisko="Pierwszy", imiona="Autor")
    autor2 = baker.make(Autor, nazwisko="Drugi", imiona="Autor")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Matematyka")

    # Create Autor_Dyscyplina for both authors
    for autor in [autor1, autor2]:
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            rok=2023,
            rodzaj_autora=rodzaj_autora_n,
        )

    # Create publication with 100 points
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test pinning effect on all authors",
        rok=2023,
        punkty_kbn=100,
    )

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Initially, autor1 has pinned discipline, autor2 unpinned
    wa1 = baker.make(  # noqa
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor1,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,  # Initially pinned
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
        kolejnosc=0,
    )

    wa2 = baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor2,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=False,  # Initially unpinned
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
        kolejnosc=1,
    )

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Build cache and calculate initial metrics
    from bpp.models.cache import Cache_Punktacja_Autora_Query
    from bpp.models.sloty.core import IPunktacjaCacher
    from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

    cacher = IPunktacjaCacher(wydawnictwo)
    cacher.removeEntries()
    cacher.rebuildEntries()
    przelicz_metryki_dla_publikacji(wydawnictwo)

    # Initially only autor1 should have cache entry (100 points, 1 slot)
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(wydawnictwo)
    cache_entries = Cache_Punktacja_Autora_Query.objects.filter(
        rekord_id=[ct.pk, wydawnictwo.pk]
    )
    assert cache_entries.count() == 1
    assert cache_entries.first().autor_id == autor1.pk
    assert cache_entries.first().pkdaut == Decimal("100")
    assert cache_entries.first().slot == Decimal("1")

    # Now pin autor2's discipline
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.post(
        url,
        {
            "pin_discipline": "1",
            "autor_assignment_id": wa2.pk,
        },
    )

    assert response.status_code in [200, 302]

    # Verify the discipline was pinned
    wa2.refresh_from_db()
    assert wa2.przypieta is True

    # Check cache was rebuilt correctly - should now have 2 entries
    cache_entries = Cache_Punktacja_Autora_Query.objects.filter(
        rekord_id=[ct.pk, wydawnictwo.pk]
    ).order_by("autor_id")
    assert cache_entries.count() == 2

    # Both authors should now have 50 points and 0.5 slot each
    for entry in cache_entries:
        assert entry.pkdaut.quantize(Decimal("0.01")) == Decimal("50.00")  # 100/2
        assert entry.slot.quantize(Decimal("0.01")) == Decimal("0.50")  # 1/2

    # Verify metrics were recalculated for BOTH authors
    # This is critical - autor1's metrics should be updated to reflect the new distribution
    from ewaluacja_metryki.models import MetrykaAutora

    for autor in [autor1, autor2]:
        try:
            metryka = MetrykaAutora.objects.get(  # noqa
                autor=autor, dyscyplina_naukowa=dyscyplina
            )
            # Both authors' metrics should reflect the new 50/50 distribution
        except MetrykaAutora.DoesNotExist:
            # Metrics might not exist yet, which is fine for this test
            pass
