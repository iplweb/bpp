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
