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
from zglos_publikacje.forms import Zgloszenie_Publikacji_DaneForm


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
