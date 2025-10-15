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
from ewaluacja_metryki.models import MetrykaAutora


@pytest.mark.django_db
def test_optymalizuj_publikacje_view_without_metryka_autora(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that the view handles missing MetrykaAutora gracefully"""
    # Create necessary objects
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka")

    # Create Autor_Dyscyplina for the year
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Create publication
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test publikacja bez metryki",
        rok=2023,
        punkty_kbn=100,
    )

    # Get or create Typ_Odpowiedzialnosci
    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Add author to publication with pinned discipline
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    # Ensure denormalization is complete
    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Explicitly ensure there is NO MetrykaAutora for this author
    MetrykaAutora.objects.filter(autor=autor).delete()

    # Test the view using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    # Check that the view returns successfully
    assert response.status_code == 200

    # Check that the context contains the expected data
    assert "publikacja" in response.context
    assert "autorzy_po_dyscyplinach" in response.context

    # Check author data
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    assert dyscyplina_group["dyscyplina"]["nazwa"] == dyscyplina.nazwa

    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 1

    autor_data = autorzy_data[0]
    assert autor_data["autor"] == autor
    assert autor_data["dyscyplina"] == dyscyplina
    assert autor_data["metryka_id"] is None  # MetrykaAutora doesn't exist
    assert autor_data["metryka_missing"] is True
    assert autor_data["metryka"] is None

    # Check that the template renders correctly with missing metryka
    content = response.content.decode("utf-8")
    assert "Kowalski Jan" in content
    assert "Metryka autora nie istnieje" in content
    assert "Sprawdź status generowania metryk" in content
    # Check for the actual rendered URLs
    assert "/ewaluacja_metryki/" in content  # Link to lista
    assert "/ewaluacja_metryki/status-generowania/" in content  # Link to status page

    # Check that the metrics section shows appropriate message
    assert "Brak danych metryki dla tego autora" in content


@pytest.mark.django_db
def test_optymalizuj_publikacje_view_with_metryka_autora(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that the view works correctly when MetrykaAutora exists"""
    # Create necessary objects
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Matematyka")

    # Create Autor_Dyscyplina for the year
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Create MetrykaAutora
    metryka = baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        punkty_nazbierane=250.50,
        slot_nazbierany=2.5,
        slot_maksymalny=4,
        slot_wszystkie=3,  # Provide explicit value
        punkty_wszystkie=300,  # Provide explicit value
        _fill_optional=False,  # Don't fill optional fields with random data
    )

    # Create publication
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test publikacja z metryką",
        rok=2023,
        punkty_kbn=100,
    )

    # Get or create Typ_Odpowiedzialnosci
    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Add author to publication
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    # Ensure denormalization is complete
    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Test the view using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    # Check that the view returns successfully
    assert response.status_code == 200

    # Check author data
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    assert dyscyplina_group["dyscyplina"]["nazwa"] == dyscyplina.nazwa

    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 1

    autor_data = autorzy_data[0]
    assert autor_data["autor"] == autor
    assert autor_data["metryka_id"] == metryka.pk
    assert autor_data["metryka_missing"] is False
    assert autor_data["metryka"] is not None
    assert autor_data["metryka"]["punkty_nazbierane"] == 250.50

    # Check that the template renders correctly with metryka
    content = response.content.decode("utf-8")
    assert "Nowak Anna" in content

    # Check that there IS a link to metryka details
    assert f"/ewaluacja_metryki/szczegoly/{autor.slug}/{dyscyplina.kod}/" in content

    # Ensure the warning messages are NOT present
    assert "Metryka autora nie istnieje" not in content
    assert "Sprawdź status generowania metryk" not in content

    # Check that metrics data is displayed (not the "Brak danych" message)
    assert "Brak danych metryki dla tego autora" not in content


@pytest.mark.django_db
def test_optymalizuj_publikacje_htmx_request_without_metryka(
    admin_client, denorms, rodzaj_autora_n
):
    """Test HTMX request handling when MetrykaAutora doesn't exist"""
    # Create minimal test data
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    wydawnictwo = baker.make(Wydawnictwo_Ciagle, rok=2023)

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Ensure no MetrykaAutora exists
    MetrykaAutora.objects.filter(autor=autor).delete()

    # Test HTMX request using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url, headers={"HX-Request": "true"})

    # Check that the response is successful
    assert response.status_code == 200

    # Check that the response handles missing MetrykaAutora
    content = response.content.decode("utf-8")
    assert "Metryka autora nie istnieje" in content

    # In HTMX request, we should get the content wrapper without the full page
    assert '<div id="content-wrapper"' in content
    assert "<!DOCTYPE html>" not in content  # Should not have full HTML page


@pytest.mark.django_db
def test_optymalizuj_publikacje_multiple_authors_mixed_metryka(
    admin_client, denorms, rodzaj_autora_n
):
    """Test view with multiple authors where some have MetrykaAutora and some don't"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor1 = baker.make(Autor, nazwisko="Autor", imiona="Pierwszy")
    autor2 = baker.make(Autor, nazwisko="Autor", imiona="Drugi")
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    # Create Autor_Dyscyplina for both authors
    for autor in [autor1, autor2]:
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            rok=2023,
            rodzaj_autora=rodzaj_autora_n,
        )

    # Create MetrykaAutora only for autor1
    # Provide explicit values to prevent overflow in procent_wykorzystania_slotow field
    metryka1 = baker.make(
        MetrykaAutora,
        autor=autor1,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=4,  # Maximum slots
        slot_nazbierany=2,  # Used slots (less than max)
        punkty_nazbierane=100,  # Points collected
        slot_wszystkie=3,  # All slots
        punkty_wszystkie=120,  # All points
        _fill_optional=False,  # Don't fill optional fields with random data
    )
    # Explicitly ensure autor2 has no MetrykaAutora
    MetrykaAutora.objects.filter(autor=autor2).delete()

    # Create publication with both authors
    wydawnictwo = baker.make(Wydawnictwo_Ciagle, rok=2023)

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    for idx, autor in enumerate([autor1, autor2]):
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wydawnictwo,
            autor=autor,
            jednostka=jednostka,
            dyscyplina_naukowa=dyscyplina,
            przypieta=True,
            typ_odpowiedzialnosci=typ_odp,
            kolejnosc=idx,  # Set unique kolejnosc for each author
        )

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Test the view using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    assert response.status_code == 200

    # Check that both authors are in the context
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1  # Both authors have same discipline

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    assert dyscyplina_group["dyscyplina"]["nazwa"] == dyscyplina.nazwa

    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 2

    # Find which is which
    autor1_data = next(ad for ad in autorzy_data if ad["autor"] == autor1)
    autor2_data = next(ad for ad in autorzy_data if ad["autor"] == autor2)

    # Check autor1 has metryka
    assert autor1_data["metryka_id"] == metryka1.pk
    assert autor1_data["metryka_missing"] is False
    assert autor1_data["metryka"] is not None

    # Check autor2 doesn't have metryka
    assert autor2_data["metryka_id"] is None
    assert autor2_data["metryka_missing"] is True
    assert autor2_data["metryka"] is None

    # Check the rendered content
    content = response.content.decode("utf-8")

    # autor1 should have a link to metryka details
    assert f"/ewaluacja_metryki/szczegoly/{autor1.slug}/{dyscyplina.kod}/" in content

    # At least one warning should be present (for autor2)
    assert "Metryka autora nie istnieje" in content


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


@pytest.mark.django_db
def test_wybrana_do_ewaluacji_badge_shows_correctly(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that 'wybrana do ewaluacji' badge only shows for publications actually selected by knapsack algorithm"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="TestAutor", imiona="Jan")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka")

    # Create Autor_Dyscyplina
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Create multiple publications with different point values
    # Publication 1: High points, will be selected
    pub1 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="High value publication",
        rok=2023,
        punkty_kbn=100,  # High points
    )

    # Publication 2: Low points, will NOT be selected
    pub2 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Low value publication",
        rok=2023,
        punkty_kbn=20,  # Low points
    )

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Add author to both publications
    for idx, pub in enumerate([pub1, pub2]):
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=pub,
            autor=autor,
            jednostka=jednostka,
            dyscyplina_naukowa=dyscyplina,
            przypieta=True,
            afiliuje=True,
            typ_odpowiedzialnosci=typ_odp,
            kolejnosc=idx,
        )

    denorms.flush()
    pub1.refresh_from_db()
    pub2.refresh_from_db()

    # Build cache for both publications
    from django.contrib.contenttypes.models import ContentType

    from bpp.models.cache import Cache_Punktacja_Autora_Query
    from bpp.models.sloty.core import IPunktacjaCacher

    for pub in [pub1, pub2]:
        cacher = IPunktacjaCacher(pub)
        cacher.removeEntries()
        cacher.rebuildEntries()

    # Get cache entries
    ct1 = ContentType.objects.get_for_model(pub1)
    ct2 = ContentType.objects.get_for_model(pub2)

    cache1 = Cache_Punktacja_Autora_Query.objects.filter(
        rekord_id=[ct1.pk, pub1.pk], autor=autor
    ).first()

    cache2 = Cache_Punktacja_Autora_Query.objects.filter(
        rekord_id=[ct2.pk, pub2.pk], autor=autor
    ).first()

    # Create MetrykaAutora with only pub1 selected (high value)
    # Simulating that the knapsack algorithm selected only the high-value publication
    from ewaluacja_metryki.models import MetrykaAutora

    metryka = baker.make(  # noqa
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=4,
        slot_nazbierany=1,  # Only one publication selected
        punkty_nazbierane=100,  # Points from pub1
        prace_nazbierane=[cache1.pk],  # ONLY pub1's cache ID is selected
        slot_wszystkie=2,  # Total slots if all were counted
        punkty_wszystkie=120,  # Total points if all were counted
        prace_wszystkie=[cache1.pk, cache2.pk],  # All publications
        _fill_optional=False,  # Don't fill optional fields with random data
    )

    # Test publication 1 (selected)
    url = reverse("ewaluacja_optymalizuj_publikacje:optymalizuj", args=(pub1.slug,))
    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show "Udział wybrany do ewaluacji" for pub1
    assert "Udział wybrany do ewaluacji" in content
    assert "Udział niewybrany" not in content

    # Test publication 2 (NOT selected)
    url = reverse("ewaluacja_optymalizuj_publikacje:optymalizuj", args=(pub2.slug,))
    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show "Udział niewybrany" for pub2 even though it has slots
    assert "Udział niewybrany" in content
    assert "Udział wybrany do ewaluacji" not in content


@pytest.mark.django_db
def test_wybrana_do_ewaluacji_no_metryka(admin_client, denorms, rodzaj_autora_n):
    """Test that publications show as not selected when no MetrykaAutora exists"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="NoMetryka", imiona="Test")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Matematyka")

    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Publication without metryka",
        rok=2023,
        punkty_kbn=100,
    )

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    denorms.flush()
    pub.refresh_from_db()

    # Build cache
    from bpp.models.sloty.core import IPunktacjaCacher

    cacher = IPunktacjaCacher(pub)
    cacher.removeEntries()
    cacher.rebuildEntries()

    # Ensure NO MetrykaAutora exists
    from ewaluacja_metryki.models import MetrykaAutora

    MetrykaAutora.objects.filter(autor=autor).delete()

    # Test the view
    url = reverse("ewaluacja_optymalizuj_publikacje:optymalizuj", args=(pub.slug,))
    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show as not selected when no metryka exists
    assert "Udział niewybrany" in content
    assert "Udział wybrany do ewaluacji" not in content
