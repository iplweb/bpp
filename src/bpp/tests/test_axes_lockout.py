"""Testy ochrony przed zgadywaniem hasła (brute-force) — django-axes.

W ``settings/test.py`` axes jest domyślnie WYŁĄCZONE (``AXES_ENABLED = False``),
bo ``Client.login()`` woła ``authenticate()`` bez ``request`` i axes podniósłby
wtedy ``AxesBackendRequestParameterRequired``, wywracając fixture'y logowania.
Dlatego każdy test, który faktycznie sprawdza lockout, MUSI jawnie włączyć axes
przez ``@override_settings(AXES_ENABLED=True)``.
"""

from datetime import timedelta

import pytest
from django.test.utils import override_settings

ADMIN_LOGIN_URL = "/admin/login/"
LOCK_USERNAME = "axes-locktest"
LOCK_PASSWORD = "correct-horse-battery-staple"


def _post_login(client, username, password):
    return client.post(
        ADMIN_LOGIN_URL,
        {"username": username, "password": password, "next": "/admin/"},
    )


@override_settings(AXES_ENABLED=True)
@pytest.mark.django_db
def test_account_ip_locked_out_after_failure_limit(client, django_user_model):
    """Po AXES_FAILURE_LIMIT nieudanych próbach para (login, IP) jest
    zablokowana — nawet POPRAWNE hasło nie loguje."""
    django_user_model.objects.create_superuser(
        username=LOCK_USERNAME,
        password=LOCK_PASSWORD,
        email="lock@example.com",
    )
    from django.conf import settings

    for _ in range(settings.AXES_FAILURE_LIMIT):
        _post_login(client, LOCK_USERNAME, "zle-haslo")

    # Sanity: dopóki nie weszło axes, ta sama (login, IP) wciąż loguje
    # poprawnym hasłem. Po przekroczeniu limitu — NIE.
    _post_login(client, LOCK_USERNAME, LOCK_PASSWORD)
    assert "_auth_user_id" not in client.session, (
        "Konto powinno być zablokowane po przekroczeniu limitu nieudanych prób, "
        "ale poprawne hasło i tak zalogowało użytkownika."
    )


@override_settings(AXES_ENABLED=True)
@pytest.mark.django_db
def test_successful_login_works_under_axes(client, django_user_model):
    """Z włączonym axes normalne logowanie poprawnym hasłem nadal działa
    (axes nie wywraca realnego widoku logowania, który przekazuje request)."""
    django_user_model.objects.create_superuser(
        username=LOCK_USERNAME,
        password=LOCK_PASSWORD,
        email="lock@example.com",
    )
    _post_login(client, LOCK_USERNAME, LOCK_PASSWORD)
    assert "_auth_user_id" in client.session, (
        "Poprawne hasło poniżej limitu prób powinno zalogować użytkownika."
    )


def test_axes_configured_with_required_policy():
    """Pin wymaganych wartości polityki: 10 prób, cooloff 1 h, lockout po
    kombinacji (login + IP) — żeby przypadkowa zmiana nie poluzowała ochrony."""
    from django.conf import settings

    assert settings.AXES_FAILURE_LIMIT == 10
    assert settings.AXES_COOLOFF_TIME == timedelta(hours=1)
    assert settings.AXES_LOCKOUT_PARAMETERS == [["username", "ip_address"]]


@override_settings(AXES_ENABLED=True)
@pytest.mark.django_db
def test_lockout_response_renderuje_szablon_bpp(client, django_user_model):
    """Po przekroczeniu limitu użytkownik dostaje pełną stronę BPP z
    komunikatem o blokadzie — a nie gołe ``HttpResponse`` z jednym zdaniem
    (domyślne zachowanie axes, gdy ``AXES_LOCKOUT_TEMPLATE`` jest ``None``)."""
    from django.conf import settings

    django_user_model.objects.create_superuser(
        username=LOCK_USERNAME,
        password=LOCK_PASSWORD,
        email="lock@example.com",
    )

    response = None
    for _ in range(settings.AXES_FAILURE_LIMIT):
        response = _post_login(client, LOCK_USERNAME, "zle-haslo")

    assert response.status_code == 429, (
        "Zablokowane logowanie powinno zwrócić 429 (AXES_HTTP_RESPONSE_CODE)."
    )
    content = response.content.decode("utf-8")
    assert "<html" in content, (
        "Odpowiedź powinna być stroną HTML z szablonu BPP, a nie gołym tekstem "
        "z domyślnego HttpResponse axes."
    )
    # Asercje celują w blok `content`, nie w `<title>`: `extratitle` renderuje
    # się wewnątrz <title> (bare.html), więc szukanie samego nagłówka w całej
    # treści przepuściłoby wypatroszenie strony do pustego layoutu.
    assert "Konto tymczasowo zablokowane</h1>" in content
    assert "60 minutach" in content, (
        "Strona ma podawać czas blokady policzony z AXES_COOLOFF_TIME."
    )
    assert "Wróć do strony głównej" in content


@pytest.mark.django_db
def test_akcja_admina_odblokowuje_konto(admin_client, django_user_model):
    """Akcja „Odblokuj konto" na liście użytkowników kasuje wpisy
    ``AccessAttempt`` wybranego użytkownika — i tylko jego."""
    from axes.models import AccessAttempt

    zablokowany = django_user_model.objects.create_user(
        username=LOCK_USERNAME, password=LOCK_PASSWORD
    )
    django_user_model.objects.create_user(username="ktos-inny", password=LOCK_PASSWORD)

    for ip in ("10.0.0.1", "10.0.0.2"):
        AccessAttempt.objects.create(
            username=LOCK_USERNAME,
            ip_address=ip,
            user_agent="pytest",
            http_accept="*/*",
            path_info=ADMIN_LOGIN_URL,
            get_data="",
            post_data="",
            failures_since_start=10,
        )
    AccessAttempt.objects.create(
        username="ktos-inny",
        ip_address="10.0.0.3",
        user_agent="pytest",
        http_accept="*/*",
        path_info=ADMIN_LOGIN_URL,
        get_data="",
        post_data="",
        failures_since_start=10,
    )

    response = admin_client.post(
        "/admin/bpp/bppuser/",
        {
            "action": "odblokuj_logowanie",
            "_selected_action": [str(zablokowany.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200

    assert not AccessAttempt.objects.filter(username=LOCK_USERNAME).exists(), (
        "Akcja powinna skasować wszystkie wpisy AccessAttempt zablokowanego "
        "użytkownika (blokada jest per (login, IP), więc wpisów bywa kilka)."
    )
    assert AccessAttempt.objects.filter(username="ktos-inny").exists(), (
        "Akcja nie powinna ruszać wpisów innych użytkowników."
    )


def _attempt(username, ip="10.0.0.1", failures=10):
    """Wiersz AccessAttempt udający zapisaną nieudaną próbę logowania."""
    from axes.models import AccessAttempt

    return AccessAttempt.objects.create(
        username=username,
        ip_address=ip,
        user_agent="pytest",
        http_accept="*/*",
        path_info=ADMIN_LOGIN_URL,
        get_data="",
        post_data="",
        failures_since_start=failures,
    )


def _uruchom_akcje(client, users):
    return client.post(
        "/admin/bpp/bppuser/",
        {
            "action": "odblokuj_logowanie",
            "_selected_action": [str(u.pk) for u in users],
        },
        follow=True,
    )


def _staff_z_uprawnieniami(django_user_model, username, codenames):
    """Staff (nie-superuser) z podanymi uprawnieniami na modelu BppUser.

    Celowo BEZ żadnej grupy: uprawnienie do modelu wystarcza, a konto bez grup
    jest najostrzejszym wariantem persony. Do niedawna taki użytkownik dostawał
    HTTP 500 na każdej stronie admina (``django_bpp/menu.py`` kasował element
    z pustej listy) — naprawione w tej samej zmianie, patrz
    ``django_bpp/tests/test_menu.py::test_uzytkownik_bez_grup_nie_wywraca_menu``.
    """
    from django.contrib.auth.models import Permission

    user = django_user_model.objects.create_user(
        username=username, password=LOCK_PASSWORD, is_staff=True
    )
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(codename=codename, content_type__app_label="bpp")
        )
    return user


@pytest.mark.django_db
def test_akcja_admina_odblokowuje_wariant_wielkosci_liter(
    admin_client, django_user_model
):
    """axes zapisuje login DOKŁADNIE tak, jak go wpisano, a LDAPBackend
    akceptuje dowolną wielkość liter i mapuje go na konto przez ``iexact``.
    Blokada zapisana jako ``JAN`` musi zniknąć przy odblokowaniu konta
    ``jan`` — inaczej w instalacji z LDAP-em akcja nic nie da."""
    from axes.models import AccessAttempt

    user = django_user_model.objects.create_user(username="jan", password=LOCK_PASSWORD)
    _attempt("JAN")

    _uruchom_akcje(admin_client, [user])

    assert not AccessAttempt.objects.filter(username__iexact="jan").exists()


@pytest.mark.django_db
def test_akcja_admina_zapisuje_wpis_w_dzienniku_admina(admin_client, django_user_model):
    """Odblokowanie musi zostawić trwały ślad w dzienniku admina — kto i kiedy
    zdjął blokadę. Sam AccessAttempt znika, a AccessFailureLog w BPP nie
    powstaje (AXES_ENABLE_ACCESS_FAILURE_LOG jest domyślnie False)."""
    from django.contrib.admin.models import LogEntry
    from django.contrib.contenttypes.models import ContentType

    user = django_user_model.objects.create_user(
        username=LOCK_USERNAME, password=LOCK_PASSWORD
    )
    _attempt(LOCK_USERNAME)

    _uruchom_akcje(admin_client, [user])

    wpisy = LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(django_user_model),
        object_id=str(user.pk),
    )
    assert wpisy.exists(), "Odblokowanie powinno trafić do dziennika admina."
    assert "dblokowano" in wpisy.first().change_message


@pytest.mark.django_db
def test_akcja_admina_odblokowuje_wszystkie_zaznaczone_konta(
    admin_client, django_user_model
):
    """Semantyka zbiorcza: implementacja obsługująca tylko pierwsze zaznaczenie
    ma tu polec."""
    from axes.models import AccessAttempt

    users = []
    for nazwa in ("pierwszy", "drugi"):
        users.append(
            django_user_model.objects.create_user(
                username=nazwa, password=LOCK_PASSWORD
            )
        )
        _attempt(nazwa)

    _uruchom_akcje(admin_client, users)

    assert not AccessAttempt.objects.filter(username__in=["pierwszy", "drugi"]).exists()


@pytest.mark.django_db
def test_akcja_admina_ostrzega_gdy_nie_bylo_blokady(admin_client, django_user_model):
    """Konto bez blokady: komunikat musi być ostrzeżeniem, a nie zielonym
    „zrobione" — inaczej administrator uzna problem za rozwiązany, choć
    przyczyna była inna (np. konto nieaktywne)."""
    from django.contrib import messages

    user = django_user_model.objects.create_user(
        username=LOCK_USERNAME, password=LOCK_PASSWORD
    )

    response = _uruchom_akcje(admin_client, [user])

    komunikaty = list(response.context["messages"])
    assert komunikaty, "Akcja powinna cokolwiek powiedzieć."
    assert komunikaty[0].level == messages.WARNING, (
        "Brak blokady do zdjęcia to nie jest sukces — poziom komunikatu ma to "
        f"odzwierciedlać, a był: {komunikaty[0].level}."
    )


@pytest.mark.django_db
def test_akcja_dziala_dla_staff_z_uprawnieniem_change(client, django_user_model):
    """Docelowa persona: osoba zarządzająca użytkownikami, BEZ uprawnień
    ``axes.*`` i bez statusu superusera."""
    from axes.models import AccessAttempt

    operator = _staff_z_uprawnieniami(
        django_user_model, "operator-change", ["change_bppuser", "view_bppuser"]
    )
    zablokowany = django_user_model.objects.create_user(
        username=LOCK_USERNAME, password=LOCK_PASSWORD
    )
    _attempt(LOCK_USERNAME)

    client.force_login(operator)
    _uruchom_akcje(client, [zablokowany])

    assert not AccessAttempt.objects.filter(username=LOCK_USERNAME).exists()


@pytest.mark.django_db
def test_akcja_niedostepna_dla_staff_bez_uprawnienia_change(client, django_user_model):
    """Granica uprawnień: sam podgląd użytkowników nie może wystarczyć do
    zdejmowania blokad logowania."""
    from axes.models import AccessAttempt

    podgladacz = _staff_z_uprawnieniami(
        django_user_model, "operator-view", ["view_bppuser"]
    )
    zablokowany = django_user_model.objects.create_user(
        username=LOCK_USERNAME, password=LOCK_PASSWORD
    )
    _attempt(LOCK_USERNAME)

    client.force_login(podgladacz)
    _uruchom_akcje(client, [zablokowany])

    assert AccessAttempt.objects.filter(username=LOCK_USERNAME).exists(), (
        "Staff z samym uprawnieniem podglądu nie powinien móc odblokować konta."
    )


@override_settings(AXES_ENABLED=True)
@pytest.mark.django_db
def test_akcja_admina_przywraca_mozliwosc_logowania(
    admin_client, client, django_user_model
):
    """Test skutku, nie stanu tabeli: po akcji zablokowany użytkownik ma się
    faktycznie zalogować poprawnym hasłem."""
    from django.conf import settings

    user = django_user_model.objects.create_superuser(
        username=LOCK_USERNAME, password=LOCK_PASSWORD, email="lock@example.com"
    )
    for _ in range(settings.AXES_FAILURE_LIMIT):
        _post_login(client, LOCK_USERNAME, "zle-haslo")
    _post_login(client, LOCK_USERNAME, LOCK_PASSWORD)
    assert "_auth_user_id" not in client.session, "Sanity: konto ma być zablokowane."

    _uruchom_akcje(admin_client, [user])

    _post_login(client, LOCK_USERNAME, LOCK_PASSWORD)
    assert "_auth_user_id" in client.session, (
        "Po zdjęciu blokady poprawne hasło powinno znów logować."
    )


def test_auth_server_nie_dziedziczy_szablonu_lockoutu():
    """Straż na poziomie źródła: ``auth_server`` ma minimalną konfigurację
    TEMPLATES (dwa context processory), więc ``base.html`` by się tam nie
    wyrenderował — dopisanie ``AXES_LOCKOUT_TEMPLATE`` do listy importów „dla
    spójności" dałoby 500 przy każdej blokadzie, wykryte dopiero gdy ktoś
    realnie się zablokuje. Modułu nie da się zaimportować w teście (wymaga
    DJANGO_BPP_SECRET_KEY), stąd sprawdzenie tekstu z pominięciem komentarzy.
    """
    from pathlib import Path

    import django_bpp.settings

    zrodlo = Path(django_bpp.settings.__file__).parent / "auth_server.py"
    kod = "\n".join(linia.split("#", 1)[0] for linia in zrodlo.read_text().splitlines())
    assert "AXES_LOCKOUT_TEMPLATE" not in kod
