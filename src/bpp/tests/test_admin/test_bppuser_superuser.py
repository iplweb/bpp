"""Status superużytkownika w adminie użytkowników zarządzają wyłącznie
superużytkownicy; staff z uprawnieniem ``change_bppuser`` nie widzi pola
``is_superuser``, nie edytuje kont superużytkowników i nie nadaje uprawnień,
których sam nie posiada."""

import pytest
from django.contrib.auth.models import Permission
from django.forms import MultiWidget
from django.urls import reverse
from model_bakery import baker

from bpp.models import BppUser

HASLO = "Haslo-testowe-123!"


def _staff(username, codenames=("change_bppuser", "view_bppuser")):
    user = BppUser.objects.create_user(username=username, password=HASLO, is_staff=True)
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get(codename=codename, content_type__app_label="bpp")
        )
    return user


def _dane_z_formularza(form):
    """POST odtworzony z bieżących wartości formularza edycji."""
    data = {}
    for bf in form:
        if bf.field.disabled:
            continue
        val = bf.value()
        widget = bf.field.widget
        if isinstance(widget, MultiWidget):
            for i, part in enumerate(widget.decompress(val)):
                data[f"{bf.html_name}_{i}"] = "" if part is None else str(part)
        elif isinstance(val, bool):
            if val:
                data[bf.html_name] = "on"
        elif isinstance(val, (list, tuple)):
            data[bf.html_name] = [str(x) for x in val]
        elif val is not None:
            data[bf.html_name] = str(val)
    return data


def _zapisz_z_dodatkami(client, user, **dodatki):
    url = reverse("admin:bpp_bppuser_change", args=(user.pk,))
    res = client.get(url)
    assert res.status_code == 200
    data = _dane_z_formularza(res.context["adminform"].form)
    data.update(dodatki)
    return client.post(url, data)


@pytest.mark.django_db
def test_nie_superuser_nie_widzi_pola_is_superuser(client):
    operator = _staff("operator", ("add_bppuser", "change_bppuser", "view_bppuser"))
    inny = baker.make(BppUser, username="inny")
    client.force_login(operator)

    for user in (operator, inny):
        res = client.get(reverse("admin:bpp_bppuser_change", args=(user.pk,)))
        assert res.status_code == 200
        assert "is_superuser" not in res.context["adminform"].form.fields

    res = client.get(reverse("admin:bpp_bppuser_add"))
    assert res.status_code == 200
    assert "is_superuser" not in res.context["adminform"].form.fields


@pytest.mark.django_db
def test_nie_superuser_nie_ustawi_is_superuser_na_wlasnym_koncie(client):
    operator = _staff("operator")
    client.force_login(operator)

    res = _zapisz_z_dodatkami(client, operator, is_superuser="on")

    assert res.status_code == 302
    operator.refresh_from_db()
    assert not operator.is_superuser


@pytest.mark.django_db
def test_nie_superuser_nie_ustawi_is_superuser_na_cudzym_koncie(client):
    operator = _staff("operator")
    inny = BppUser.objects.create_user(username="inny", password=HASLO)
    client.force_login(operator)

    res = _zapisz_z_dodatkami(client, inny, is_superuser="on", first_name="Jan")

    assert res.status_code == 302
    inny.refresh_from_db()
    assert inny.first_name == "Jan"
    assert not inny.is_superuser


@pytest.mark.django_db
def test_nie_superuser_nie_edytuje_konta_superusera(client):
    operator = _staff("operator")
    szef = BppUser.objects.create_superuser(
        username="szef", password=HASLO, email="szef@example.com"
    )
    client.force_login(operator)

    url = reverse("admin:bpp_bppuser_change", args=(szef.pk,))
    client.post(url, {"username": "szef", "first_name": "Zmienione"})
    szef.refresh_from_db()
    assert szef.first_name != "Zmienione"

    res = client.get(url)
    if res.status_code == 200:
        # tylko podgląd (has_view_permission) — bez możliwości zapisu
        assert not res.context["has_change_permission"]


@pytest.mark.django_db
def test_nie_superuser_nie_zmieni_hasla_superusera(client):
    operator = _staff("operator")
    szef = BppUser.objects.create_superuser(
        username="szef", password=HASLO, email="szef@example.com"
    )
    client.force_login(operator)

    url = reverse("admin:auth_user_password_change", args=(szef.pk,))
    nowe = "Inne-haslo-456!"
    res = client.post(
        url,
        {"password1": nowe, "password2": nowe, "usable_password": "true"},
    )

    assert res.status_code in (403, 404)
    szef.refresh_from_db()
    assert szef.check_password(HASLO)


@pytest.mark.django_db
def test_nie_superuser_nie_usunie_superusera(client):
    operator = _staff("operator", ("change_bppuser", "view_bppuser", "delete_bppuser"))
    szef = BppUser.objects.create_superuser(
        username="szef", password=HASLO, email="szef@example.com"
    )
    client.force_login(operator)

    client.post(reverse("admin:bpp_bppuser_delete", args=(szef.pk,)), {"post": "yes"})
    assert BppUser.objects.filter(pk=szef.pk).exists()

    client.post(
        reverse("admin:bpp_bppuser_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [str(szef.pk)],
            "post": "yes",
        },
    )
    assert BppUser.objects.filter(pk=szef.pk).exists()


@pytest.mark.django_db
def test_nie_superuser_usuwa_zwyklego_uzytkownika(client):
    operator = _staff("operator", ("change_bppuser", "view_bppuser", "delete_bppuser"))
    zwykly = BppUser.objects.create_user(username="zwykly", password=HASLO)
    client.force_login(operator)

    client.post(reverse("admin:bpp_bppuser_delete", args=(zwykly.pk,)), {"post": "yes"})
    assert not BppUser.objects.filter(pk=zwykly.pk).exists()


@pytest.mark.django_db
def test_odblokuj_logowanie_pomija_superuserow_dla_nie_superusera(client):
    from axes.models import AccessAttempt

    operator = _staff("operator")
    szef = BppUser.objects.create_superuser(
        username="szef", password=HASLO, email="szef@example.com"
    )
    AccessAttempt.objects.create(
        username="szef",
        ip_address="10.0.0.1",
        user_agent="pytest",
        http_accept="*/*",
        path_info="/admin/login/",
        get_data="",
        post_data="",
        failures_since_start=10,
    )
    client.force_login(operator)

    client.post(
        reverse("admin:bpp_bppuser_changelist"),
        {"action": "odblokuj_logowanie", "_selected_action": [str(szef.pk)]},
    )

    assert AccessAttempt.objects.filter(username="szef").exists()


@pytest.mark.django_db
def test_nie_superuser_nie_nada_uprawnien_ktorych_nie_ma(client):
    operator = _staff("operator")
    inny = BppUser.objects.create_user(username="inny", password=HASLO)
    obce = Permission.objects.get(
        codename="delete_bppuser", content_type__app_label="bpp"
    )
    wlasne = Permission.objects.get(
        codename="view_bppuser", content_type__app_label="bpp"
    )
    client.force_login(operator)

    res = client.get(reverse("admin:bpp_bppuser_change", args=(inny.pk,)))
    qs = res.context["adminform"].form.fields["user_permissions"].queryset
    assert wlasne in qs
    assert obce not in qs

    _zapisz_z_dodatkami(client, inny, user_permissions=[str(obce.pk), str(wlasne.pk)])
    inny.refresh_from_db()
    assert not inny.user_permissions.filter(pk=obce.pk).exists()


@pytest.mark.django_db
def test_nie_superuser_zachowuje_istniejace_obce_uprawnienia(client):
    operator = _staff("operator")
    obce = Permission.objects.get(
        codename="delete_bppuser", content_type__app_label="bpp"
    )
    inny = BppUser.objects.create_user(username="inny", password=HASLO)
    inny.user_permissions.add(obce)
    client.force_login(operator)

    res = _zapisz_z_dodatkami(client, inny, first_name="Jan")

    assert res.status_code == 302
    inny.refresh_from_db()
    assert inny.first_name == "Jan"
    assert inny.user_permissions.filter(pk=obce.pk).exists()


@pytest.mark.django_db
def test_superuser_nadal_ustawia_is_superuser(admin_client):
    inny = BppUser.objects.create_user(username="inny", password=HASLO)

    res = admin_client.get(reverse("admin:bpp_bppuser_change", args=(inny.pk,)))
    assert "is_superuser" in res.context["adminform"].form.fields

    res = _zapisz_z_dodatkami(admin_client, inny, is_superuser="on")

    assert res.status_code == 302
    inny.refresh_from_db()
    assert inny.is_superuser


@pytest.mark.django_db
def test_nie_superuser_nie_doda_konta_superusera(client):
    operator = _staff("operator", ("add_bppuser", "change_bppuser", "view_bppuser"))
    client.force_login(operator)

    client.post(
        reverse("admin:bpp_bppuser_add"),
        {
            "username": "nowy",
            "usable_password": "true",
            "password1": HASLO,
            "password2": HASLO,
            "is_superuser": "on",
            "is_staff": "on",
        },
    )

    nowy = BppUser.objects.get(username="nowy")
    assert not nowy.is_superuser
