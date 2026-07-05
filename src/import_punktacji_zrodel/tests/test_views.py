import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from import_punktacji_zrodel.models import ImportPunktacjiZrodel


@pytest.mark.django_db
def test_index_wymaga_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(username="u1", password="x")
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:index"))
    assert resp.status_code in (403, 302)  # brak grupy


@pytest.mark.django_db
def test_index_dostepny_dla_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(username="u2", password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:index"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_formularz_nowego_importu_get(client, django_user_model):
    user = django_user_model.objects.create_user(username="u3", password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:new"))
    assert resp.status_code == 200
    assert b"plik" in resp.content.lower()


def _user_w_grupie(django_user_model, username):
    user = django_user_model.objects.create_user(username=username, password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    return user


@pytest.mark.django_db
def test_router_zakonczony_sukcesem_redirect_na_wyniki(client, django_user_model):
    from django.utils import timezone

    user = _user_w_grupie(django_user_model, "ur1")
    client.force_login(user)
    teraz = timezone.now()
    imp = baker.make(
        ImportPunktacjiZrodel,
        owner=user,
        rok=2025,
        started_on=teraz,
        finished_on=teraz,
        finished_successfully=True,
    )
    resp = client.get(
        reverse("import_punktacji_zrodel:importpunktacjizrodel-router", args=[imp.pk])
    )
    assert resp.status_code == 302
    assert resp.url == reverse(
        "import_punktacji_zrodel:importpunktacjizrodel-results", args=[imp.pk]
    )


@pytest.mark.django_db
def test_router_w_trakcie_redirect_na_szczegoly(client, django_user_model):
    from django.utils import timezone

    user = _user_w_grupie(django_user_model, "ur2")
    client.force_login(user)
    imp = baker.make(
        ImportPunktacjiZrodel,
        owner=user,
        rok=2025,
        started_on=timezone.now(),
        finished_on=None,
    )
    resp = client.get(
        reverse("import_punktacji_zrodel:importpunktacjizrodel-router", args=[imp.pk])
    )
    assert resp.status_code == 302
    assert resp.url == reverse(
        "import_punktacji_zrodel:importpunktacjizrodel-details", args=[imp.pk]
    )


@pytest.mark.django_db
def test_strona_przetwarzania_ma_fallback_refresh(client, django_user_model):
    # Strona "przetwarzanie" (details) dla operacji w toku ma awaryjny
    # meta-refresh na router, by przejść na wyniki bez websocketu.
    from django.utils import timezone

    user = _user_w_grupie(django_user_model, "ur3")
    client.force_login(user)
    imp = baker.make(
        ImportPunktacjiZrodel,
        owner=user,
        rok=2025,
        started_on=timezone.now(),
        finished_on=None,
    )
    resp = client.get(
        reverse("import_punktacji_zrodel:importpunktacjizrodel-details", args=[imp.pk])
    )
    assert resp.status_code == 200
    assert b'http-equiv="refresh"' in resp.content
    router_url = reverse(
        "import_punktacji_zrodel:importpunktacjizrodel-router", args=[imp.pk]
    )
    assert router_url.encode() in resp.content


@pytest.mark.django_db
def test_zatwierdz_get_zwraca_405(client, django_user_model):
    user = django_user_model.objects.create_user(username="u4", password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    client.force_login(user)
    imp = baker.make(ImportPunktacjiZrodel, owner=user)
    url = reverse("import_punktacji_zrodel:zatwierdz", args=[imp.pk])
    resp = client.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_zatwierdz_wymaga_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(username="u5", password="x")
    client.force_login(user)
    imp = baker.make(ImportPunktacjiZrodel, owner=user)
    url = reverse("import_punktacji_zrodel:zatwierdz", args=[imp.pk])
    resp = client.post(url)
    assert resp.status_code in (403, 302)
