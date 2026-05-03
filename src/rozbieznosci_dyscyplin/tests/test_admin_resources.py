"""Testy klas Resource (eksport django-import-export)."""

import pytest
from model_bakery import baker

from bpp.models import Dyscyplina_Zrodla, Wydawnictwo_Ciagle
from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView


@pytest.mark.django_db
def test_rozbieznosci_view_resource_get_site_url():
    """Test RozbieznosciViewResource.get_site_url."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciViewResource

    site = Site.objects.first()
    if site is None:
        site = Site.objects.create(domain="example.com", name="Example")

    resource = RozbieznosciViewResource()
    url = resource.get_site_url()

    assert url.startswith("https://")
    assert site.domain in url


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_resource_get_site_url():
    """Test RozbieznosciZrodelViewResource.get_site_url."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciZrodelViewResource

    site = Site.objects.first()
    if site is None:
        site = Site.objects.create(domain="example.com", name="Example")

    resource = RozbieznosciZrodelViewResource()
    url = resource.get_site_url()

    assert url.startswith("https://")
    assert site.domain in url


@pytest.mark.django_db
def test_rozbieznosci_view_resource_dehydrate_bpp_strona_url(zle_przypisana_praca):
    """Test RozbieznosciViewResource.dehydrate_bpp_strona_url."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciViewResource

    site = Site.objects.first()
    if site is None:
        Site.objects.create(domain="example.com", name="Example")

    rozbieznosc = RozbieznosciView.objects.first()
    assert rozbieznosc is not None

    resource = RozbieznosciViewResource()
    url = resource.dehydrate_bpp_strona_url(rozbieznosc)

    assert "browse_praca" in url or "bpp" in url


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_resource_dehydrate_dyscypliny_zrodla(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
):
    """Test RozbieznosciZrodelViewResource.dehydrate_dyscypliny_zrodla."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciZrodelViewResource

    Site.objects.get_or_create(pk=1, defaults={"domain": "example.com", "name": "Ex"})

    # Utworz rozbieznosc zrodel
    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    wc.dodaj_autora(autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1)

    rozbieznosc = RozbieznosciZrodelView.objects.first()
    assert rozbieznosc is not None

    resource = RozbieznosciZrodelViewResource()
    disciplines = resource.dehydrate_dyscypliny_zrodla(rozbieznosc)

    # Powinno zawierac nazwe dyscypliny2
    assert dyscyplina2.nazwa in disciplines
