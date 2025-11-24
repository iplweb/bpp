import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia


@pytest.fixture
def uczelnia():
    """Fixture creating a university instance."""
    return baker.make(Uczelnia, nazwa="Testowa Uczelnia")


@pytest.mark.django_db
def test_unpinning_list_url_accessible(client, admin_user, uczelnia):
    """Test that unpinning list URL is accessible."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:unpinning-list")
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_unpinning_list_default_sort_params(client, admin_user, uczelnia):
    """Test that default sorting parameters are punkty_b and desc."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:unpinning-list")
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["sort_by"] == "punkty_b"
    assert response.context["sort_dir"] == "desc"


@pytest.mark.django_db
def test_unpinning_list_custom_sort_params_in_context(client, admin_user, uczelnia):
    """Test that custom sort parameters are passed to template context."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:unpinning-list")
    response = client.get(url, {"sort_by": "autor_a", "sort_dir": "asc"})

    assert response.status_code == 200
    assert response.context["sort_by"] == "autor_a"
    assert response.context["sort_dir"] == "asc"


@pytest.mark.django_db
def test_unpinning_list_sort_by_tytul(client, admin_user, uczelnia):
    """Test sorting by tytul parameter."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:unpinning-list")
    response = client.get(url, {"sort_by": "tytul", "sort_dir": "asc"})

    assert response.status_code == 200
    assert response.context["sort_by"] == "tytul"
    assert response.context["sort_dir"] == "asc"


@pytest.mark.django_db
def test_unpinning_list_sort_direction_desc(client, admin_user, uczelnia):
    """Test descending sort direction."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:unpinning-list")
    response = client.get(url, {"sort_by": "punkty_a", "sort_dir": "desc"})

    assert response.status_code == 200
    assert response.context["sort_dir"] == "desc"


@pytest.mark.django_db
def test_unpinning_list_all_sort_columns(client, admin_user, uczelnia):
    """Test that all expected sort columns are accepted without errors."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:unpinning-list")

    sort_columns = [
        "tytul",
        "punktacja",
        "dyscyplina",
        "autor_a",
        "slots_missing",
        "slot_in_work",
        "punkty_a",
        "sloty_a",
        "punkty_b",
        "sloty_b",
        "autor_b",
        "makes_sense",
    ]

    for column in sort_columns:
        response = client.get(url, {"sort_by": column, "sort_dir": "asc"})
        assert response.status_code == 200, f"Failed for column: {column}"
        assert response.context["sort_by"] == column


@pytest.mark.django_db
def test_unpinning_list_preserves_filter_with_sort(client, admin_user, uczelnia):
    """Test that sorting preserves filter parameters."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:unpinning-list")

    response = client.get(
        url, {"only_sensible": "1", "sort_by": "tytul", "sort_dir": "asc"}
    )

    assert response.status_code == 200
    assert response.context["only_sensible"] is True
    assert response.context["sort_by"] == "tytul"
    assert response.context["sort_dir"] == "asc"
