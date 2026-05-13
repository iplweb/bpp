import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH

URL = "bpp:zapytanie"


@pytest.fixture
def wprowadzanie_user(test_user):
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    test_user.groups.add(group)
    test_user.is_staff = True
    test_user.save()
    return test_user


@pytest.fixture
def wprowadzanie_client(client, wprowadzanie_user):
    client.force_login(wprowadzanie_user)
    return client


@pytest.mark.django_db
def test_zapytanie_view_anonymous_redirected(client):
    response = client.get(reverse(URL))
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_zapytanie_view_logged_in_non_staff_forbidden(client, test_user):
    client.force_login(test_user)
    response = client.get(reverse(URL))
    assert response.status_code == 403


@pytest.mark.django_db
def test_zapytanie_view_staff_without_group_forbidden(client, test_user):
    test_user.is_staff = True
    test_user.save()
    client.force_login(test_user)
    response = client.get(reverse(URL))
    assert response.status_code == 403


@pytest.mark.django_db
def test_zapytanie_view_group_without_staff_forbidden(client, test_user):
    """Staff jest wymagany oprocz przynaleznosci do grupy."""
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    test_user.groups.add(group)
    client.force_login(test_user)
    response = client.get(reverse(URL))
    assert response.status_code == 403


@pytest.mark.django_db
def test_zapytanie_view_wprowadzanie_user_allowed(wprowadzanie_client):
    response = wprowadzanie_client.get(reverse(URL))
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_zapytanie_view_superuser_allowed(superuser_client):
    response = superuser_client.get(reverse(URL))
    assert response.status_code == 200


@pytest.mark.django_db
def test_zapytanie_view_renders_radio_buttons(superuser_client):
    response = superuser_client.get(reverse(URL))
    html = response.content.decode("utf-8")
    assert 'type="radio"' in html
    assert 'value="rekord"' in html
    assert 'value="autor"' in html


@pytest.mark.django_db
def test_zapytanie_query_autor_matches(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")

    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Kowalski"'},
    )
    assert response.status_code == 200
    assert response.context["count"] == 1
    assert response.context["error"] is None
    results = list(response.context["results"])
    assert len(results) == 1
    assert results[0].nazwisko == "Kowalski"


@pytest.mark.django_db
def test_zapytanie_query_autor_no_matches(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski")

    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nazwisko = "Nieistnieje"'},
    )
    assert response.status_code == 200
    assert response.context["count"] == 0
    assert response.context["error"] is None


@pytest.mark.django_db
def test_zapytanie_query_invalid_syntax_shows_error(superuser_client):
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": "this is not valid djangoql !!!"},
    )
    assert response.status_code == 200
    assert response.context["error"]
    assert response.context["count"] is None


@pytest.mark.django_db
def test_zapytanie_query_unknown_field_shows_error(superuser_client):
    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'nieistniejace_pole = "x"'},
    )
    assert response.status_code == 200
    assert response.context["error"]


@pytest.mark.django_db
def test_zapytanie_empty_query_renders_form_without_results(superuser_client):
    response = superuser_client.get(reverse(URL), {"model": "autor", "query": ""})
    assert response.status_code == 200
    assert response.context.get("results") is None


@pytest.mark.django_db
def test_zapytanie_query_rekord_uses_correct_model(superuser_client):
    """Radio 'rekord' przelacza queryset na model Rekord, nie Autor."""
    response = superuser_client.get(
        reverse(URL),
        {"model": "rekord", "query": "rok = 1900"},
    )
    assert response.status_code == 200
    assert response.context["error"] is None
    assert response.context["model_key"] == "rekord"
    assert response.context["count"] == 0


@pytest.mark.django_db
def test_zapytanie_default_model_is_rekord(superuser_client):
    response = superuser_client.get(reverse(URL))
    assert response.status_code == 200
    form = response.context["form"]
    assert form.fields["model"].initial == "rekord"
