"""FD#513: importer a UKRYTY język.

Po masowym ukryciu języków źródło (CrossRef, autodetekcja) może wskazać
język, którego nie ma na liście wyboru kroku „Weryfikacja”. Dawniej pole
„Język” zostawało wtedy puste bez słowa wyjaśnienia."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Jezyk
from importer_publikacji.models import ImportSession
from importer_publikacji.views.publikacja import _resolve_jezyk


def _jezyk(skrot, **kw):
    return baker.make(Jezyk, nazwa=f"język {skrot}", skrot=skrot, **kw)


@pytest.fixture
def bez_kodu_xq(db):
    Jezyk.objects.filter(kod_bcp47__istartswith="xq").delete()
    Jezyk.objects.filter(skrot_crossref="xq").delete()


def test_ukryty_ze_skrotem_nie_przeslania_widocznego_z_kodem_bcp47(bez_kodu_xq):
    """Importer szuka najpierw wśród WIDOCZNYCH po obu polach."""
    _jezyk("t-uk", skrot_crossref="xq", kod_bcp47="", widoczny=False)
    widoczny = _jezyk("t-wi", skrot_crossref=None, kod_bcp47="xq", widoczny=True)
    assert _resolve_jezyk("xq") == widoczny


def test_krok_weryfikacji_wyjasnia_ukryty_jezyk(
    importer_client, importer_user, bez_kodu_xq
):
    ukryty = _jezyk("t-uk", kod_bcp47="xq", widoczny=False)
    assert _resolve_jezyk("xq") == ukryty  # jedyny pasujący
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/fd513",
        raw_data={},
        normalized_data={"title": "Test", "doi": None, "year": 2024},
        status=ImportSession.Status.FETCHED,
        jezyk=ukryty,
    )

    resp = importer_client.get(
        reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})
    )
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert f"Źródło podaje język „{ukryty.nazwa}”" in tresc
    assert "Pokaż zaznaczone" in tresc
    # Ukrytego języka nie ma na liście wyboru.
    assert ukryty not in resp.context["form"].fields["jezyk"].queryset


def test_krok_weryfikacji_bez_komunikatu_dla_widocznego_jezyka(
    importer_client, importer_user, bez_kodu_xq
):
    widoczny = _jezyk("t-wi", kod_bcp47="xq", widoczny=True)
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/fd513b",
        raw_data={},
        normalized_data={"title": "Test", "doi": None, "year": 2024},
        status=ImportSession.Status.FETCHED,
        jezyk=widoczny,
    )
    resp = importer_client.get(
        reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})
    )
    assert resp.status_code == 200
    assert "Źródło podaje język" not in resp.content.decode()
