"""Track 3 (audyt uczelnia 2026-06-04): wizard zgłaszania publikacji nie może
crashować w instalacji multi-hosted.

``Zgloszenie_Publikacji_DaneForm`` przy braku ``uczelnia`` robiło
``Uczelnia.objects.get()`` (→ ``MultipleObjectsReturned`` przy >1 uczelni),
a ``Zgloszenie_Publikacji.clean`` (walidacja opłat) używała ``self._uczelnia``,
które NIGDY nie było ustawiane → ta sama awaria. Forma musi przepisać uczelnię
oglądającego na ``instance._uczelnia``.
"""

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import Uczelnia
from zglos_publikacje.forms import (
    Zgloszenie_Publikacji_DaneForm,
    Zgloszenie_Publikacji_KosztPublikacjiForm,
)


@pytest.fixture
def dwie_uczelnie(db, uczelnia):
    site = baker.make(Site, domain="druga-zgl.testserver", name="druga-zgl")
    uczelnia2 = Uczelnia.objects.create(skrot="DR3", nazwa="Druga uczelnia", site=site)
    return uczelnia, uczelnia2


@pytest.mark.django_db
def test_daneform_przepisuje_uczelnie_na_instancje(dwie_uczelnie):
    """Forma ustawia ``instance._uczelnia`` na przekazaną uczelnię — żeby
    ``model.clean`` nie zgadywał (i nie crashował) w multi-hosted."""
    uczelnia1, _uczelnia2 = dwie_uczelnie

    form = Zgloszenie_Publikacji_DaneForm(uczelnia=uczelnia1)

    assert form.instance._uczelnia == uczelnia1


# Dane do kroku 4 (opłaty) — komplet pól wymaganych przez clean_*.
KOSZT_DANE = {
    "opl_pub_cost_free": "true",
    "opl_pub_research_potential": "false",
    "opl_pub_research_or_development_projects": "false",
    "opl_pub_other": "false",
    "opl_pub_amount": "",
}


@pytest.mark.django_db
def test_kosztform_przepisuje_uczelnie_na_instancje(dwie_uczelnie):
    """Krok 4 (opłaty) też musi przekazać uczelnię na ``instance._uczelnia`` —
    inaczej ``model.clean`` zgaduje przez ``Uczelnia.objects.get()``."""
    uczelnia1, _ = dwie_uczelnie

    form = Zgloszenie_Publikacji_KosztPublikacjiForm(uczelnia=uczelnia1)

    assert form.instance._uczelnia == uczelnia1


@pytest.mark.django_db
def test_kosztform_walidacja_nie_crashuje_multi_hosted(dwie_uczelnie):
    """Regresja Rollbar #400: ``is_valid()`` na kroku 4 odpala ``model.clean``,
    które przy >1 uczelni robiło ``Uczelnia.objects.get()`` →
    ``MultipleObjectsReturned``. Z przekazaną uczelnią nie może crashować."""
    uczelnia1, _ = dwie_uczelnie

    form = Zgloszenie_Publikacji_KosztPublikacjiForm(
        data=KOSZT_DANE, uczelnia=uczelnia1
    )

    # Nie może rzucić MultipleObjectsReturned podczas walidacji modelu.
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_kosztform_bez_uczelni_nie_crashuje_multi_hosted(dwie_uczelnie):
    """Defense-in-depth: nawet bez przekazanej uczelni walidacja kroku 4 nie
    może rzucić ``MultipleObjectsReturned`` — fallback ``model.clean`` używa
    ``get_single_uczelnia_or_none()`` (zwraca ``None``, nie zgaduje)."""
    form = Zgloszenie_Publikacji_KosztPublikacjiForm(data=KOSZT_DANE)

    # Samo wywołanie nie może wybuchnąć na zgadywaniu uczelni.
    form.is_valid()
