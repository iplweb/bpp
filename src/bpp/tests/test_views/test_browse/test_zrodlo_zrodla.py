import re

import pytest
from django.urls import reverse
from model_bakery import baker


def test_zrodlo_browser_pokazuj_zrodla_bez_prac(client, zrodlo, uczelnia):
    uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych = True
    uczelnia.save()

    res = client.get(reverse("bpp:browse_zrodla"))
    assert zrodlo.nazwa in res.rendered_content


def test_zrodlo_browser_nie_pokazuj_zrodel_bez_prac(client, zrodlo, uczelnia):

    uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych = False
    uczelnia.save()

    res = client.get(reverse("bpp:browse_zrodla"))
    assert zrodlo.nazwa not in str(res.rendered_content)


@pytest.mark.django_db
def test_zrodlo_view_shows_banner_when_no_publications(client, zrodlo):
    """Test that ZrodloView shows a banner when source has no publications"""
    # Source without publications
    res = client.get(reverse("bpp:browse_zrodlo", args=(zrodlo.slug,)))
    assert res.status_code == 200
    assert "Brak publikacji" in res.rendered_content
    assert "To źródło nie zawiera jeszcze żadnych prac" in res.rendered_content


@pytest.mark.django_db
def test_zrodlo_view_no_banner_when_has_publications(client, zrodlo):
    """Test that ZrodloView doesn't show banner when source has publications"""
    # Add a publication to the source
    from bpp.models import Wydawnictwo_Ciagle

    baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)

    res = client.get(reverse("bpp:browse_zrodlo", args=(zrodlo.slug,)))
    assert res.status_code == 200
    assert "Brak publikacji" not in res.rendered_content
    assert "To źródło nie zawiera jeszcze żadnych prac" not in res.rendered_content


def _accordion_items_with_years(content):
    """Zwraca listę krotek (klasa <li>, rok) dla panelu dyscyplin."""
    return re.findall(
        r'<li class="(accordion-item[^"]*)"[^>]*>.*?Rok\s+(\d+)',
        content,
        re.DOTALL,
    )


@pytest.mark.django_db
def test_zrodlo_view_pokazuje_dyscypliny_najnowszego_roku_z_bazy(
    client, zrodlo, dyscyplina1
):
    """Rok nowszy niż dawny twardy limit (2025) musi się pojawić na podstronie
    źródła i być domyślnie rozwinięty (Freshdesk 296)."""
    from bpp.models import Dyscyplina_Zrodla

    for rok in (2024, 2025, 2026):
        Dyscyplina_Zrodla.objects.create(zrodlo=zrodlo, dyscyplina=dyscyplina1, rok=rok)

    res = client.get(reverse("bpp:browse_zrodlo", args=(zrodlo.slug,)))
    assert res.status_code == 200

    content = res.rendered_content
    assert "Rok 2026" in content

    items = dict((rok, klasa) for klasa, rok in _accordion_items_with_years(content))
    # Najnowszy rok (2026) rozwinięty domyślnie...
    assert "is-active" in items["2026"]
    # ...a poprzednie lata zwinięte (brak twardego dowiązania do 2025).
    assert "is-active" not in items["2025"]
    assert "is-active" not in items["2024"]
