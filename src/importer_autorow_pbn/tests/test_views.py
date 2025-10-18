import json

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from importer_autorow_pbn.models import DoNotRemind
from pbn_api.models import Scientist


@pytest.mark.django_db
def test_main_view_requires_staff(client, normal_django_user):
    """Test that main view requires staff member"""
    client.force_login(normal_django_user)
    url = reverse("importer_autorow_pbn:main")
    response = client.get(url)
    assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_main_view_accessible_to_staff(client, admin_user):
    """Test that main view is accessible to staff members"""
    client.force_login(admin_user)
    url = reverse("importer_autorow_pbn:main")
    response = client.get(url)
    assert response.status_code == 200
    assert "Importer autorów PBN" in response.content.decode()


@pytest.mark.django_db
def test_main_view_shows_unmatched_scientists(client, admin_user, create_scientist):
    """Test that main view shows scientists without BPP equivalents"""
    client.force_login(admin_user)

    # Create scientists using fixture
    scientist_without_match = create_scientist(  # noqa
        mongoId="scientist1", lastName="Kowalski", name="Jan"
    )

    scientist_with_match = create_scientist(  # noqa
        mongoId="scientist2", lastName="Nowak", name="Anna"
    )

    # Create Autor linked to scientist2
    baker.make(Autor, pbn_uid_id="scientist2")

    url = reverse("importer_autorow_pbn:main")
    response = client.get(url)

    content = response.content.decode()
    assert "Kowalski" in content
    assert "Nowak" not in content  # Should not show matched scientist


@pytest.mark.django_db
def test_main_view_excludes_ignored_scientists(client, admin_user, create_scientist):
    """Test that main view excludes ignored scientists"""
    client.force_login(admin_user)

    # Create scientists using fixture
    scientist1 = create_scientist(mongoId="scientist1", lastName="Kowalski", name="Jan")

    scientist2 = create_scientist(  # noqa
        mongoId="scientist2", lastName="Nowak", name="Anna"
    )  # noqa

    # Ignore scientist1
    baker.make(DoNotRemind, scientist=scientist1)

    url = reverse("importer_autorow_pbn:main")
    response = client.get(url)

    content = response.content.decode()
    assert "Kowalski" not in content  # Ignored
    assert "Nowak" in content  # Not ignored


@pytest.mark.django_db
def test_main_view_search(client, admin_user, create_scientist):
    """Test search functionality in main view"""
    client.force_login(admin_user)

    # Create scientists using fixture
    scientist1 = create_scientist(  # noqa
        mongoId="scientist1", lastName="Kowalski", name="Jan"
    )  # noqa

    scientist2 = create_scientist(  # noqa
        mongoId="scientist2", lastName="Nowak", name="Anna"
    )  # noqa

    url = reverse("importer_autorow_pbn:main")

    # Search for Kowalski
    response = client.get(url, {"q": "Kowalski"})
    content = response.content.decode()
    assert "Kowalski" in content
    assert "Nowak" not in content

    # Search for Anna
    response = client.get(url, {"q": "Anna"})
    content = response.content.decode()
    assert "Kowalski" not in content
    assert "Nowak" in content


@pytest.mark.django_db
def test_ignore_scientist_endpoint(client, admin_user):
    """Test AJAX endpoint for ignoring a scientist"""
    client.force_login(admin_user)

    scientist = baker.make(
        Scientist, mongoId="scientist1", lastName="Kowalski", name="Jan"
    )

    url = reverse("importer_autorow_pbn:ignore_scientist", args=[scientist.mongoId])

    response = client.post(url, {"reason": "Test ignore reason"})

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"

    # Check that DoNotRemind was created
    assert DoNotRemind.objects.filter(scientist=scientist).exists()
    do_not_remind = DoNotRemind.objects.get(scientist=scientist)
    assert do_not_remind.reason == "Test ignore reason"
    assert do_not_remind.ignored_by == admin_user


@pytest.mark.django_db
def test_ignore_scientist_already_ignored(client, admin_user):
    """Test ignoring an already ignored scientist"""
    client.force_login(admin_user)

    scientist = baker.make(Scientist, mongoId="scientist1")
    baker.make(DoNotRemind, scientist=scientist)

    url = reverse("importer_autorow_pbn:ignore_scientist", args=[scientist.mongoId])

    response = client.post(url, {"reason": "Another reason"})

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "already_ignored"


@pytest.mark.django_db
def test_link_scientist_endpoint(client, admin_user):
    """Test AJAX endpoint for linking a scientist to an Autor"""
    client.force_login(admin_user)

    scientist = baker.make(
        Scientist, mongoId="scientist1", lastName="Kowalski", name="Jan"
    )

    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")

    url = reverse("importer_autorow_pbn:link_scientist", args=[scientist.mongoId])

    response = client.post(url, {"autor_id": str(autor.pk)})

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "success"

    # Check that Autor was linked
    autor.refresh_from_db()
    assert autor.pbn_uid_id == scientist.mongoId


@pytest.mark.django_db
def test_link_scientist_no_autor_id(client, admin_user):
    """Test linking without providing autor_id"""
    client.force_login(admin_user)

    scientist = baker.make(Scientist, mongoId="scientist1")

    url = reverse("importer_autorow_pbn:link_scientist", args=[scientist.mongoId])

    response = client.post(url, {})

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "error"
    assert "No autor_id provided" in data["message"]


@pytest.mark.django_db
def test_link_scientist_autor_not_found(client, admin_user):
    """Test linking to non-existent Autor"""
    client.force_login(admin_user)

    scientist = baker.make(Scientist, mongoId="scientist1")

    url = reverse("importer_autorow_pbn:link_scientist", args=[scientist.mongoId])

    response = client.post(url, {"autor_id": "99999"})  # Non-existent ID

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "error"
    assert "Autor not found" in data["message"]


@pytest.mark.django_db
def test_link_scientist_autor_already_linked(client, admin_user):
    """Test linking to Autor that already has different PBN UID"""
    client.force_login(admin_user)

    scientist = baker.make(Scientist, mongoId="scientist1")
    # Create another scientist that is already linked
    different_scientist = baker.make(Scientist, mongoId="different_scientist")

    # Autor already linked to different scientist
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", pbn_uid_id=different_scientist.mongoId
    )

    url = reverse("importer_autorow_pbn:link_scientist", args=[scientist.mongoId])

    response = client.post(url, {"autor_id": str(autor.pk)})

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "error"
    assert "already linked to different PBN UID" in data["message"]


@pytest.mark.django_db
def test_views_require_login(client):
    """Test that all views require login"""
    scientist = baker.make(Scientist, mongoId="scientist1")

    urls = [
        reverse("importer_autorow_pbn:main"),
        reverse("importer_autorow_pbn:ignore_scientist", args=[scientist.mongoId]),
        reverse("importer_autorow_pbn:link_scientist", args=[scientist.mongoId]),
    ]

    for url in urls:
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login
        assert "/login/" in response.url or "/accounts/login/" in response.url
