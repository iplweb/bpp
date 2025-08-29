import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from deduplikator_autorow.views import (
    duplicate_authors_view,
    mark_non_duplicate,
    reset_skipped_authors,
    scal_autorow_view,
)

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH

User = get_user_model()


@pytest.mark.django_db
def test_duplicate_authors_view_requires_authentication():
    """Test that duplicate_authors_view requires authentication"""
    from django.contrib.auth.models import AnonymousUser

    factory = RequestFactory()
    request = factory.get("/duplicate-authors/")

    # Create anonymous user
    request.user = AnonymousUser()
    request.session = {}

    try:
        response = duplicate_authors_view(request)
        # Should redirect to login, not raise PermissionDenied
        assert response.status_code in [302, 401]  # redirect to login or unauthorized
    except PermissionDenied:
        # This is also acceptable - decorator can raise PermissionDenied
        pass


@pytest.mark.django_db
def test_duplicate_authors_view_requires_group():
    """Test that duplicate_authors_view requires GR_WPROWADZANIE_DANYCH group"""
    factory = RequestFactory()
    request = factory.get("/duplicate-authors/")

    # Create authenticated user without the required group
    user = User.objects.create_user("testuser", password="testpass")
    request.user = user
    request.session = {}

    try:
        response = duplicate_authors_view(request)  # noqa
        raise AssertionError("Should have raised PermissionDenied")
    except PermissionDenied:
        pass  # Expected


@pytest.mark.django_db
def test_duplicate_authors_view_allows_user_with_group():
    """Test that duplicate_authors_view allows users with GR_WPROWADZANIE_DANYCH group"""
    factory = RequestFactory()
    request = factory.get("/duplicate-authors/")

    # Create authenticated user with the required group
    user = User.objects.create_user("testuser", password="testpass")
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    request.user = user
    request.session = {}

    try:
        # This should not raise PermissionDenied
        response = duplicate_authors_view(request)  # noqa
        # The view itself might return errors due to missing data, but should not be blocked by permissions
        assert True
    except PermissionDenied:
        raise AssertionError(
            "Should not have raised PermissionDenied for user with correct group"
        )


@pytest.mark.django_db
def test_duplicate_authors_view_allows_superuser():
    """Test that duplicate_authors_view allows superusers even without group"""
    factory = RequestFactory()
    request = factory.get("/duplicate-authors/")

    # Create superuser
    user = User.objects.create_superuser("admin", "admin@test.com", "adminpass")
    request.user = user
    request.session = {}

    try:
        # This should not raise PermissionDenied
        response = duplicate_authors_view(request)  # noqa
        # The view itself might return errors due to missing data, but should not be blocked by permissions
        assert True
    except PermissionDenied:
        raise AssertionError("Should not have raised PermissionDenied for superuser")


@pytest.mark.django_db
def test_scal_autorow_view_requires_group():
    """Test that scal_autorow_view requires GR_WPROWADZANIE_DANYCH group"""
    factory = RequestFactory()
    request = factory.post("/scal-autorow/")

    # Create authenticated user without the required group
    user = User.objects.create_user("testuser", password="testpass")
    request.user = user

    try:
        response = scal_autorow_view(request)  # noqa
        raise AssertionError("Should have raised PermissionDenied")
    except PermissionDenied:
        pass  # Expected


@pytest.mark.django_db
def test_mark_non_duplicate_requires_group():
    """Test that mark_non_duplicate requires GR_WPROWADZANIE_DANYCH group"""
    factory = RequestFactory()
    request = factory.post("/mark-non-duplicate/")

    # Create authenticated user without the required group
    user = User.objects.create_user("testuser", password="testpass")
    request.user = user

    try:
        response = mark_non_duplicate(request)  # noqa
        raise AssertionError("Should have raised PermissionDenied")
    except PermissionDenied:
        pass  # Expected


@pytest.mark.django_db
def test_reset_skipped_authors_requires_group():
    """Test that reset_skipped_authors requires GR_WPROWADZANIE_DANYCH group"""
    factory = RequestFactory()
    request = factory.get("/reset-skipped-authors/")

    # Create authenticated user without the required group
    user = User.objects.create_user("testuser", password="testpass")
    request.user = user
    request.session = {}

    try:
        response = reset_skipped_authors(request)  # noqa
        raise AssertionError("Should have raised PermissionDenied")
    except PermissionDenied:
        pass  # Expected
