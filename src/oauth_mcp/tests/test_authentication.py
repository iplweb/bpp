import pytest


@pytest.mark.django_db
def test_wazny_token_ustawia_usera(access_token, client):
    user, tok = access_token()
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    # whoami powstaje w Task 5; tu sprawdzamy tylko że NIE ma 500/anon-degrade.
    assert resp.status_code in (200, 404)


@pytest.mark.django_db
def test_niewazny_bearer_daje_401_nie_anon(access_token, client):
    # dowolny anonimowy read-only endpoint api_v1 z GŁUPIM bearerem → 401
    resp = client.get(
        "/api/v1/wydawnictwo_ciagle/",
        HTTP_AUTHORIZATION="Bearer nieistniejacy-token",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_brak_bearera_dalej_anonimowo(client):
    resp = client.get("/api/v1/wydawnictwo_ciagle/")
    assert resp.status_code == 200  # AnonReadOnly bez zmian


@pytest.mark.django_db
def test_token_bez_read_scope_odrzucony(access_token, client):
    # Uwaga reviewera #6: token bez zakresu 'read' NIE może przejść jako
    # ważny bearer — inaczej deklarowany scope 'read' to pozorna izolacja,
    # a każdy przyszły scope (np. 'write') byłby nieegzekwowany.
    user, tok = access_token(scope="")  # token bez żadnego scope
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_token_z_read_scope_akceptowany(access_token, client):
    # Regres: prawidłowy token z 'read' dalej działa (200), nie regresujemy.
    user, tok = access_token(scope="read")
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert resp.status_code == 200
