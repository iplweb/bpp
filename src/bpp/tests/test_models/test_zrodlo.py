import pytest

from bpp.models import Dyscyplina_Zrodla


def test_Dyscyplina_Zrodla___str__(zrodlo, dyscyplina1):
    dz = Dyscyplina_Zrodla.objects.create(
        zrodlo=zrodlo, dyscyplina=dyscyplina1, rok=2017
    )
    assert (
        str(dz)
        == 'Przypisanie dyscypliny "memetyka stosowana (3.1)" do źródła "Testowe Źródło" dla roku 2017'
    )


@pytest.mark.django_db
def test_dyscypliny_aktualna_ewaluacja_pokazuje_najnowszy_rok(zrodlo, dyscyplina1):
    """Najnowszy rok obecny w bazie musi się pojawić, nawet gdy jest nowszy
    niż dawny twardy limit PBN_AKTUALNA_EWALUACJA_STOP (Freshdesk 296)."""
    for rok in (2024, 2025, 2026):
        Dyscyplina_Zrodla.objects.create(zrodlo=zrodlo, dyscyplina=dyscyplina1, rok=rok)

    lata = list(zrodlo.dyscypliny_aktualna_ewaluacja().values_list("rok", flat=True))

    assert 2026 in lata
    assert max(lata) == 2026


@pytest.mark.django_db
def test_dyscypliny_aktualna_ewaluacja_pomija_lata_przed_oknem(zrodlo, dyscyplina1):
    """Dolna granica okna ewaluacji jest zachowana — stare lata się nie pokazują."""
    Dyscyplina_Zrodla.objects.create(zrodlo=zrodlo, dyscyplina=dyscyplina1, rok=2018)
    Dyscyplina_Zrodla.objects.create(zrodlo=zrodlo, dyscyplina=dyscyplina1, rok=2024)

    lata = list(zrodlo.dyscypliny_aktualna_ewaluacja().values_list("rok", flat=True))

    assert 2018 not in lata
    assert 2024 in lata
