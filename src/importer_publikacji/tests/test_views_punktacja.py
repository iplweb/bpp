from decimal import Decimal

import pytest
from model_bakery import baker


@pytest.fixture
def _sesja_ciagla(importer_user):
    from bpp.models import Punktacja_Zrodla, Zrodlo
    from importer_publikacji.models import ImportSession

    zrodlo = baker.make(Zrodlo)
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=2024, punkty_kbn=Decimal(140))
    return ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1/x",
        raw_data={},
        normalized_data={"year": 2024, "title": "T", "authors": []},
        zrodlo=zrodlo,
        jest_wydawnictwem_zwartym=False,
        status=ImportSession.Status.AUTHORS_MATCHED,
    )


@pytest.mark.django_db
def test_punktacja_get_proponuje_z_zrodla(_sesja_ciagla, importer_client):
    from django.urls import reverse

    url = reverse("importer_publikacji:punktacja", args=[_sesja_ciagla.pk])
    resp = importer_client.get(url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert b"140" in resp.content  # sugestia widoczna czarno na bialym


@pytest.mark.django_db
def test_punktacja_post_zapisuje_i_idzie_do_review(_sesja_ciagla, importer_client):
    from django.urls import reverse

    url = reverse("importer_publikacji:punktacja", args=[_sesja_ciagla.pk])
    resp = importer_client.post(url, {"punkty_kbn": "100"})
    assert resp.status_code == 200
    _sesja_ciagla.refresh_from_db()
    assert _sesja_ciagla.matched_data.get("punkty_kbn") == "100"
    assert _sesja_ciagla.status == _sesja_ciagla.Status.PUNKTACJA
