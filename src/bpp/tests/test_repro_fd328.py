"""Repro dla FD#328 — kopiowanie rekordu przyciskiem „toż".

Klikniecie „toż" na rekordzie powiazanym z PBN (ustawione pbn_uid)
konczylo sie HTTP 500, bo kopia probowala zachowac ten sam pbn_uid
(OneToOneField, unique=True) -> IntegrityError przy save().

https://iplweb.freshdesk.com/a/tickets/328
"""

import pytest
from model_bakery import baker

from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.views.admin import WydawnictwoCiagleTozView, WydawnictwoZwarteTozView
from pbn_api.models.publication import Publication


@pytest.mark.django_db
def test_toz_zwarte_z_pbn_uid_nie_rzuca_integrity_error():
    pub = baker.make(Publication, mongoId="fd328-zwarte-pub")
    z1 = baker.make(Wydawnictwo_Zwarte, pbn_uid=pub)
    assert Wydawnictwo_Zwarte.objects.count() == 1

    url = WydawnictwoZwarteTozView().get_redirect_url(z1.pk)

    assert Wydawnictwo_Zwarte.objects.count() == 2
    z2 = Wydawnictwo_Zwarte.objects.exclude(pk=z1.pk).get()
    assert z2.pbn_uid_id is None
    assert str(z2.pk) in url


@pytest.mark.django_db
def test_toz_ciagle_z_pbn_uid_nie_rzuca_integrity_error():
    pub = baker.make(Publication, mongoId="fd328-ciagle-pub")
    c1 = baker.make(Wydawnictwo_Ciagle, pbn_uid=pub)
    assert Wydawnictwo_Ciagle.objects.count() == 1

    url = WydawnictwoCiagleTozView().get_redirect_url(c1.pk)

    assert Wydawnictwo_Ciagle.objects.count() == 2
    c2 = Wydawnictwo_Ciagle.objects.exclude(pk=c1.pk).get()
    assert c2.pbn_uid_id is None
    assert str(c2.pk) in url
