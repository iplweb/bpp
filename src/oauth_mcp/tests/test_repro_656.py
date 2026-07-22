"""Sprzątanie osieroconych rejestracji DCR (#656).

Otwarta rejestracja klientów MCP (RFC 7591) tworzy `Application` przy każdym
udanym żądaniu, ale nic nigdy tych wierszy nie usuwało — tabela rosła
monotonicznie. Te testy pilnują OBU stron kontraktu:

1. rejestracja DCR oznacza się rozstrzygalnie (prefiks `dcr-` w `client_id`),
2. sprzątacz kasuje wyłącznie rejestracje, które NIGDY nie doszły do skutku.

Najgroźniejszy regres to punkt 2: `Application` kaskaduje na
AccessToken/RefreshToken/Grant/IDToken, więc błędne dopasowanie filtra nie
zostawia śmiecia — wylogowuje realnego użytkownika.
"""

import json
from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_grant_model,
    get_refresh_token_model,
)

from oauth_mcp.tasks import (
    DCR_CLIENT_ID_PREFIX,
    DCR_RETENCJA_DNI,
    usun_osierocone_aplikacje_dcr,
)


def _aplikacja_dcr(*, dni_temu, client_id=None, **kwargs):
    """Rejestracja w stylu DCR, sztucznie postarzona o `dni_temu` dni.

    `created` ma `auto_now_add=True`, więc daty nie da się podać przy
    tworzeniu — trzeba ją nadpisać osobnym UPDATE-em, omijając ORM-owe auto.
    """
    Application = get_application_model()
    kwargs.setdefault("client_type", Application.CLIENT_PUBLIC)
    kwargs.setdefault("authorization_grant_type", Application.GRANT_AUTHORIZATION_CODE)
    kwargs.setdefault("redirect_uris", "https://claude.ai/cb")
    kwargs.setdefault("name", "mcp-client")
    if client_id is not None:
        kwargs["client_id"] = client_id
    app = Application.objects.create(**kwargs)
    Application.objects.filter(pk=app.pk).update(
        created=timezone.now() - timedelta(days=dni_temu)
    )
    app.refresh_from_db()
    return app


@pytest.mark.django_db
def test_dcr_oznacza_client_id_rozstrzygalnym_prefiksem(client):
    """Rejestracja przez /o/register/ musi dać się odróżnić od ręcznej.

    Generator DOT (`ClientIdGenerator`) losuje z UNICODE_ASCII_CHARACTER_SET —
    same alfanumeryki, BEZ myślnika. Prefiks `dcr-` jest więc niemożliwy do
    wygenerowania przypadkowo, a nie tylko „mało prawdopodobny".
    """
    resp = client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": ["https://claude.ai/cb"]}),
        content_type="application/json",
    )
    assert resp.status_code == 201

    client_id = resp.json()["client_id"]
    assert client_id.startswith(DCR_CLIENT_ID_PREFIX)

    Application = get_application_model()
    assert Application.objects.filter(client_id=client_id).exists()


@pytest.mark.django_db
def test_kasuje_osierocona_rejestracje_dcr():
    Application = get_application_model()
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI + 1,
        client_id=DCR_CLIENT_ID_PREFIX + "osierocona",
    )

    assert usun_osierocone_aplikacje_dcr() == 1
    assert not Application.objects.filter(pk=app.pk).exists()


@pytest.mark.django_db
def test_nie_kasuje_swiezej_rejestracji():
    """Klient w trakcie flow (zarejestrował się przed chwilą) musi przeżyć."""
    Application = get_application_model()
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI - 1,
        client_id=DCR_CLIENT_ID_PREFIX + "swieza",
    )

    assert usun_osierocone_aplikacje_dcr() == 0
    assert Application.objects.filter(pk=app.pk).exists()


@pytest.mark.django_db
def test_nie_kasuje_aplikacji_z_waznym_access_tokenem(django_user_model):
    """NAJGROŹNIEJSZY REGRES: skasowanie kaskaduje na token → wylogowanie.

    Aplikacja jest stara i ma prefiks DCR — jedyne, co ją chroni, to fakt, że
    ktoś realnie dokończył flow i ma ważny token.
    """
    Application = get_application_model()
    AccessToken = get_access_token_model()

    user = baker.make(django_user_model)
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI * 10,
        client_id=DCR_CLIENT_ID_PREFIX + "uzywana",
        user=user,
    )
    AccessToken.objects.create(
        user=user,
        application=app,
        token="tok-656",
        expires=timezone.now() + timedelta(hours=1),
        scope="read",
    )

    assert usun_osierocone_aplikacje_dcr() == 0
    assert Application.objects.filter(pk=app.pk).exists()
    assert AccessToken.objects.filter(application=app).exists()


@pytest.mark.django_db
def test_nie_kasuje_aplikacji_z_refresh_tokenem(django_user_model):
    """Access token wygasa po 30 min, refresh żyje 7 dni — sam też chroni."""
    Application = get_application_model()
    RefreshToken = get_refresh_token_model()

    user = baker.make(django_user_model)
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI * 10,
        client_id=DCR_CLIENT_ID_PREFIX + "refresh",
        user=user,
    )
    RefreshToken.objects.create(user=user, application=app, token="rt-656")

    assert usun_osierocone_aplikacje_dcr() == 0
    assert Application.objects.filter(pk=app.pk).exists()


@pytest.mark.django_db
def test_nie_kasuje_aplikacji_z_grantem(django_user_model):
    """Grant żyje minuty, ale to znaczy „flow trwa TERAZ" — nie ruszać."""
    Application = get_application_model()
    Grant = get_grant_model()

    user = baker.make(django_user_model)
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI * 10,
        client_id=DCR_CLIENT_ID_PREFIX + "grant",
        user=user,
    )
    Grant.objects.create(
        user=user,
        application=app,
        code="code-656",
        expires=timezone.now() + timedelta(minutes=5),
        redirect_uri="https://claude.ai/cb",
        scope="read",
    )

    assert usun_osierocone_aplikacje_dcr() == 0
    assert Application.objects.filter(pk=app.pk).exists()


@pytest.mark.django_db
def test_nie_kasuje_integracji_zalozonej_recznie(django_user_model):
    """Integracja wpisana ręcznie w adminie NIE MOŻE zniknąć.

    Nie ma prefiksu DCR, więc domyślne kryteria jej nie dotykają — nawet gdy
    jest stara, publiczna, authorization-code i nigdy nieużywana (typowy stan
    integracji przygotowanej „na zapas", przed pierwszym logowaniem).
    """
    Application = get_application_model()
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI * 100,
        client_id="RecznieZalozonaIntegracja123",
        name="integracja-uczelni",
    )

    assert usun_osierocone_aplikacje_dcr() == 0
    assert Application.objects.filter(pk=app.pk).exists()


@pytest.mark.django_db
def test_dry_run_liczy_ale_nie_kasuje():
    Application = get_application_model()
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI + 1,
        client_id=DCR_CLIENT_ID_PREFIX + "dry",
    )

    assert usun_osierocone_aplikacje_dcr(dry_run=True) == 1
    assert Application.objects.filter(pk=app.pk).exists()


@pytest.mark.django_db
def test_nieoznaczone_legacy_tylko_na_wyrazne_zyczenie(django_user_model):
    """Wiersze sprzed wprowadzenia prefiksu — heurystyka pod jawną flagą.

    Rejestracje DCR utworzone PRZED tą zmianą nie mają prefiksu i nie da się
    ich odróżnić inaczej niż heurystyką (public + authorization-code + brak
    właściciela). Heurystyka jest krucha, więc domyślnie wyłączona.
    """
    Application = get_application_model()
    legacy = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI + 1,
        client_id="StaraRejestracjaBezPrefiksu",
        user=None,
    )
    # Ręczna integracja ma właściciela — heurystyka musi ją ominąć.
    recznie = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI + 1,
        client_id="RecznaZWlascicielem",
        user=baker.make(django_user_model),
    )

    assert usun_osierocone_aplikacje_dcr() == 0

    assert usun_osierocone_aplikacje_dcr(uwzglednij_nieoznaczone=True) == 1
    assert not Application.objects.filter(pk=legacy.pk).exists()
    assert Application.objects.filter(pk=recznie.pk).exists()


@pytest.mark.django_db
def test_komenda_zarzadzajaca_dziala():
    from io import StringIO

    from django.core.management import call_command

    Application = get_application_model()
    app = _aplikacja_dcr(
        dni_temu=DCR_RETENCJA_DNI + 1,
        client_id=DCR_CLIENT_ID_PREFIX + "cli",
    )

    out = StringIO()
    call_command("usun_osierocone_aplikacje_oauth", "--dry-run", stdout=out)
    assert "1" in out.getvalue()
    assert Application.objects.filter(pk=app.pk).exists()

    call_command("usun_osierocone_aplikacje_oauth", stdout=StringIO())
    assert not Application.objects.filter(pk=app.pk).exists()
