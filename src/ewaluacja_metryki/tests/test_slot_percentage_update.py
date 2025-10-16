from decimal import Decimal

import pytest
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
from bpp.models.sloty.core import IPunktacjaCacher
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
from ewaluacja_metryki.utils import oblicz_metryki_dla_autora


@pytest.mark.django_db
def test_procent_wykorzystania_slotow_updates_correctly(denorms, rodzaj_autora_n):
    """Test that slot utilization percentage is correctly calculated and updated"""

    # Create test data
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

    # Set maximum slots for the author
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4"),  # Maximum 4 slots
        ilosc_udzialow_monografie=Decimal("1"),  # Required field
    )

    # Create publications
    pub1 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Publication 1",
        rok=2023,
        punkty_kbn=100,
    )

    pub2 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Publication 2",
        rok=2023,
        punkty_kbn=50,
    )

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Add author to publications
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

    # Build cache
    for pub in [pub1, pub2]:
        denorms.flush()
        pub.refresh_from_db()
        cacher = IPunktacjaCacher(pub)
        cacher.removeEntries()
        cacher.rebuildEntries()

    # Calculate metrics
    metryka, created = oblicz_metryki_dla_autora(
        autor=autor,
        dyscyplina=dyscyplina,
        rok_min=2022,
        rok_max=2025,
    )

    # Verify the percentage was calculated
    assert metryka.procent_wykorzystania_slotow is not None
    assert metryka.procent_wykorzystania_slotow > 0

    # Verify the calculation is correct
    expected_percentage = (metryka.slot_nazbierany / metryka.slot_maksymalny) * 100
    assert metryka.procent_wykorzystania_slotow == expected_percentage

    # Update metrics again (simulating pin/unpin scenario)
    metryka2, created = oblicz_metryki_dla_autora(
        autor=autor,
        dyscyplina=dyscyplina,
        rok_min=2022,
        rok_max=2025,
    )

    # Verify it's an update, not create
    assert not created
    assert metryka2.pk == metryka.pk

    # Verify percentage is still correctly calculated
    assert metryka2.procent_wykorzystania_slotow is not None
    expected_percentage2 = (metryka2.slot_nazbierany / metryka2.slot_maksymalny) * 100
    assert metryka2.procent_wykorzystania_slotow == expected_percentage2


@pytest.mark.django_db
def test_procent_wykorzystania_handles_zero_slot_maksymalny(rodzaj_autora_n):
    """Test that percentage calculation handles zero slot_maksymalny gracefully"""

    jednostka = baker.make(Jednostka, skupia_pracownikow=True)  # noqa
    autor = baker.make(Autor, nazwisko="ZeroSlot", imiona="Test")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Matematyka")

    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Don't create IloscUdzialowDlaAutoraZaCalosc - will default to 4
    # But we'll test with slot_maksymalny=0 case

    # Calculate metrics with forced slot_maksymalny=0
    metryka, created = oblicz_metryki_dla_autora(
        autor=autor,
        dyscyplina=dyscyplina,
        rok_min=2022,
        rok_max=2025,
        slot_maksymalny=Decimal("0"),  # Force zero
    )

    # Should handle gracefully
    assert metryka.procent_wykorzystania_slotow == Decimal("0")
    assert metryka.srednia_za_slot_nazbierana == Decimal("0")


@pytest.mark.django_db
def test_averages_calculated_correctly(rodzaj_autora_n):
    """Test that average points per slot are calculated correctly"""

    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="Average", imiona="Test")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Fizyka")

    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Create IloscUdzialowDlaAutoraZaCalosc entry (required after fix)
    baker.make(
        IloscUdzialowDlaAutoraZaCalosc,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        ilosc_udzialow=Decimal("4"),
        ilosc_udzialow_monografie=Decimal("2"),
    )

    # Create a publication
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Publication",
        rok=2023,
        punkty_kbn=200,  # 200 points
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

    from bpp.models.sloty.core import IPunktacjaCacher

    cacher = IPunktacjaCacher(pub)
    cacher.removeEntries()
    cacher.rebuildEntries()

    # Calculate metrics
    metryka, _ = oblicz_metryki_dla_autora(
        autor=autor,
        dyscyplina=dyscyplina,
        rok_min=2022,
        rok_max=2025,
    )

    # Check averages are calculated
    assert metryka.srednia_za_slot_nazbierana is not None
    assert metryka.srednia_za_slot_wszystkie is not None

    # Verify calculation
    if metryka.slot_nazbierany > 0:
        expected_avg_nazbierane = metryka.punkty_nazbierane / metryka.slot_nazbierany
        assert metryka.srednia_za_slot_nazbierana == expected_avg_nazbierane

    if metryka.slot_wszystkie > 0:
        expected_avg_wszystkie = metryka.punkty_wszystkie / metryka.slot_wszystkie
        assert metryka.srednia_za_slot_wszystkie == expected_avg_wszystkie
