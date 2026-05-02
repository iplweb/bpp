"""Title filtering tests for pbn_wysylka_oswiadczen app."""

import pytest
from django.urls import reverse

from pbn_wysylka_oswiadczen.queries import get_publications_queryset

from ._helpers import create_user_with_group


@pytest.mark.django_db
def test_get_publications_queryset_title_filter(publication_with_pbn_uid):
    """Test title filtering in get_publications_queryset."""
    # Should find with matching title
    ciagle_qs, zwarte_qs = get_publications_queryset(
        rok_od=2022, rok_do=2022, tytul="of ionic"
    )
    assert ciagle_qs.count() == 1

    # Should not find with non-matching title
    ciagle_qs, zwarte_qs = get_publications_queryset(
        rok_od=2022, rok_do=2022, tytul="nonexistent"
    )
    assert ciagle_qs.count() == 0


@pytest.mark.django_db
def test_get_publications_queryset_title_filter_case_insensitive(
    publication_with_pbn_uid,
):
    """Test title filtering is case-insensitive."""
    ciagle_qs, _ = get_publications_queryset(rok_od=2022, rok_do=2022, tytul="OF IONIC")
    assert ciagle_qs.count() == 1


@pytest.mark.django_db
def test_main_view_title_filter(client, uczelnia, publication_with_pbn_uid):
    """Test main view with title filter shows correct count."""
    user = create_user_with_group()
    client.force_login(user)

    response = client.get(
        reverse("pbn_wysylka_oswiadczen:main"),
        {"rok_od": 2022, "rok_do": 2022, "tytul": "of ionic"},
    )
    assert response.status_code == 200
    assert response.context["total_count"] == 1
    assert response.context["tytul"] == "of ionic"
