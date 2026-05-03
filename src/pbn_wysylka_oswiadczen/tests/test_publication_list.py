"""PublicationListView tests for pbn_wysylka_oswiadczen app."""

import pytest
from django.urls import reverse

from ._helpers import create_user_with_group


@pytest.mark.django_db
def test_publication_list_view_basic(client, uczelnia, publication_with_pbn_uid):
    """Test PublicationListView returns publications."""
    user = create_user_with_group()
    client.force_login(user)

    response = client.get(
        reverse("pbn_wysylka_oswiadczen:publications"),
        {"rok_od": 2022, "rok_do": 2022},
    )
    assert response.status_code == 200
    assert "page_obj" in response.context
    assert response.context["page_obj"].paginator.count == 1


@pytest.mark.django_db
def test_publication_list_view_with_title_filter(
    client, uczelnia, publication_with_pbn_uid
):
    """Test PublicationListView with title filter."""
    user = create_user_with_group()
    client.force_login(user)

    # With matching title
    response = client.get(
        reverse("pbn_wysylka_oswiadczen:publications"),
        {"rok_od": 2022, "rok_do": 2022, "tytul": "of ionic"},
    )
    assert response.context["page_obj"].paginator.count == 1

    # With non-matching title
    response = client.get(
        reverse("pbn_wysylka_oswiadczen:publications"),
        {"rok_od": 2022, "rok_do": 2022, "tytul": "nonexistent"},
    )
    assert response.context["page_obj"].paginator.count == 0


@pytest.mark.django_db
def test_publication_list_view_requires_auth(client):
    """Test PublicationListView requires authentication."""
    response = client.get(reverse("pbn_wysylka_oswiadczen:publications"))
    assert response.status_code == 302
    assert "login" in response.url
