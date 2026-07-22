import pytest


@pytest.mark.django_db
def test_post_z_bearerem_blokowany_403(access_token, client):
    user, tok = access_token()
    resp = client.post(
        "/api/v1/raport_slotow_uczelnia/",
        data={},
        HTTP_AUTHORIZATION=f"Bearer {tok.token}",
        content_type="application/json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_get_z_bearerem_przechodzi_przez_middleware(access_token, client):
    user, tok = access_token()
    resp = client.get(
        "/api/v1/wydawnictwo_ciagle/",
        HTTP_AUTHORIZATION=f"Bearer {tok.token}",
    )
    # middleware nie blokuje GET; sam endpoint może dać 200
    assert resp.status_code != 403


@pytest.mark.django_db
def test_post_bez_bearera_nietkniety(client):
    # bez tokenu middleware nie ingeruje; endpoint (per-view [Basic] +
    # IsAuthenticated) sam odrzuca anonima → 401 z DRF, NIE 403 z middleware.
    resp = client.post(
        "/api/v1/raport_slotow_uczelnia/", data={}, content_type="application/json"
    )
    assert resp.status_code == 401
