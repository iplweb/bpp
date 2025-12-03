"""Tests for selection badges and discipline metrics in ewaluacja_optymalizuj_publikacje."""

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
    metryka = baker.make(  # noqa
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=4,
        slot_nazbierany=1,  # Only one publication selected
        punkty_nazbierane=100,  # Points from pub1
        prace_nazbierane=[cache1.rekord_id],  # ONLY pub1's rekord_id is selected
        slot_wszystkie=2,  # Total slots if all were counted
        punkty_wszystkie=120,  # Total points if all were counted
        prace_wszystkie=[cache1.rekord_id, cache2.rekord_id],  # All publications
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
    MetrykaAutora.objects.filter(autor=autor).delete()

    # Test the view
    url = reverse("ewaluacja_optymalizuj_publikacje:optymalizuj", args=(pub.slug,))
    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show as not selected when no metryka exists
    assert "Udział niewybrany" in content
    assert "Udział wybrany do ewaluacji" not in content


@pytest.mark.django_db
def test_author_with_multiple_disciplines_shows_correct_metric(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that view shows correct MetrykaAutora when author has metrics for multiple disciplines"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="MultiDiscipline", imiona="Test")

    # Create TWO different disciplines
    dyscyplina_informatyka = baker.make(
        Dyscyplina_Naukowa, nazwa="Informatyka", kod="1.6"
    )
    dyscyplina_matematyka = baker.make(
        Dyscyplina_Naukowa, nazwa="Matematyka", kod="1.1"
    )

    # Create Autor_Dyscyplina for ONLY Informatyka in 2023
    # (Author can only have one primary discipline per year)
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina_informatyka,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Create MetrykaAutora for BOTH disciplines with different values
    metryka_informatyka = baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina_informatyka,
        jednostka=jednostka,
        punkty_nazbierane=Decimal("200.00"),  # Different values to distinguish
        slot_nazbierany=Decimal("2.0"),
        slot_maksymalny=Decimal("4.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("250.00"),
        _fill_optional=False,
    )

    metryka_matematyka = baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina_matematyka,
        jednostka=jednostka,
        punkty_nazbierane=Decimal("150.00"),  # Different values to distinguish
        slot_nazbierany=Decimal("1.5"),
        slot_maksymalny=Decimal("4.0"),
        slot_wszystkie=Decimal("2.5"),
        punkty_wszystkie=Decimal("180.00"),
        _fill_optional=False,
    )

    # Create publication with author assigned to INFORMATYKA discipline ONLY
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test publication for Informatyka",
        rok=2023,
        punkty_kbn=100,
    )

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_informatyka,  # INFORMATYKA discipline
        przypieta=True,
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Test the view
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    assert response.status_code == 200

    # Verify the context contains the CORRECT metric for Informatyka
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    assert dyscyplina_group["dyscyplina"]["nazwa"] == "Informatyka"
    assert dyscyplina_group["dyscyplina"]["kod"] == "1.6"

    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 1

    autor_data = autorzy_data[0]
    assert autor_data["autor"] == autor
    assert autor_data["dyscyplina"] == dyscyplina_informatyka

    # CRITICAL: Verify the metryka_id matches the Informatyka metric, NOT Matematyka
    assert autor_data["metryka_id"] == metryka_informatyka.pk, (
        "Should use Informatyka metric"
    )
    assert autor_data["metryka_id"] != metryka_matematyka.pk, (
        "Should NOT use Matematyka metric"
    )
    assert autor_data["metryka_missing"] is False

    # Verify the metryka data matches Informatyka values
    assert autor_data["metryka"] is not None
    assert autor_data["metryka"]["punkty_nazbierane"] == Decimal("200.00")
    assert autor_data["metryka"]["sloty_wypelnione"] == Decimal("2.0")

    # Verify the template shows correct data
    content = response.content.decode("utf-8")
    assert "MultiDiscipline Test" in content
    assert "Informatyka" in content

    # Verify the correct link to metryka details (using Informatyka kod)
    assert f"/ewaluacja_metryki/szczegoly/{autor.slug}/1.6/" in content
    # Should NOT have link to Matematyka
    assert f"/ewaluacja_metryki/szczegoly/{autor.slug}/1.1/" not in content


@pytest.mark.django_db
def test_author_without_wymiar_etatu_no_default_4_slots(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that authors without wymiar_etatu don't get default 4 slots assigned"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="BezWymiaru", imiona="Test")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka", kod="1.6")

    # Create Autor_Dyscyplina WITHOUT wymiar_etatu
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
        wymiar_etatu=None,  # Explicitly no wymiar_etatu
        procent_dyscypliny=None,  # No percentage either
    )

    # Create publication
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test publication for author without wymiar_etatu",
        rok=2023,
        punkty_kbn=100,
    )

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
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Build cache
    from bpp.models.sloty.core import IPunktacjaCacher

    cacher = IPunktacjaCacher(wydawnictwo)
    cacher.removeEntries()
    cacher.rebuildEntries()

    # Try to recalculate metrics - should NOT create MetrykaAutora with default 4 slots
    from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

    przelicz_metryki_dla_publikacji(wydawnictwo)

    # Verify that MetrykaAutora was NOT created with default 4 slots
    metryka_exists = MetrykaAutora.objects.filter(
        autor=autor, dyscyplina_naukowa=dyscyplina
    ).exists()

    # Should NOT exist because author has no wymiar_etatu and no IloscUdzialowDlaAutoraZaCalosc entry
    assert not metryka_exists, (
        "MetrykaAutora should NOT be created for authors without wymiar_etatu"
    )

    # Test the view to ensure it marks this as missing data
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    assert response.status_code == 200

    # Check that the view correctly identifies missing data
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 1

    autor_data = autorzy_data[0]
    assert autor_data["autor"] == autor
    assert autor_data["metryka_missing"] is True
    assert autor_data["autor_dyscyplina_missing_data"] is True, (
        "Should flag missing wymiar_etatu and IloscUdzialowDlaAutoraZaCalosc"
    )

    # Verify the template shows appropriate warnings
    content = response.content.decode("utf-8")
    assert "BezWymiaru Test" in content
    assert "Metryka autora nie istnieje" in content
