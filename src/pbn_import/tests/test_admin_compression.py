import pytest
from django.test import override_settings
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
@override_settings(
    COMPRESS_ENABLED=True,
    COMPRESS_OFFLINE=False,
)
def test_import_session_admin_renders_with_compression_enabled(admin_client):
    """
    Test that ImportSession admin changelist page renders successfully
    with Django compression enabled.

    This test catches the bug where pbn_import/css/admin.css is missing
    because the Grunt task wasn't configured to build it.

    If the CSS file doesn't exist (because Grunt didn't build it), Django
    compressor will raise UncompressableFileError when trying to render
    the admin page.
    """
    # Create an ImportSession object to display in the admin
    baker.make(
        "pbn_import.ImportSession",
        status="pending",
        current_step="initial",
        progress_percentage=0,
    )

    # Get the admin changelist URL for ImportSession
    url = reverse("admin:pbn_import_importsession_changelist")

    # Try to render the admin page with compression enabled
    # This will fail with UncompressableFileError if admin.css doesn't exist
    response = admin_client.get(url)

    # Assert successful render
    assert response.status_code == 200
    assert (
        b"Import Sessions" in response.content
        or b"import session" in response.content.lower()
    )


@pytest.mark.django_db
@override_settings(
    COMPRESS_ENABLED=True,
    COMPRESS_OFFLINE=False,
)
def test_import_session_admin_detail_renders_with_compression(admin_client):
    """
    Test that ImportSession admin detail/change page renders successfully
    with Django compression enabled.

    This provides additional coverage for the admin.css compression issue
    by testing the detail view where custom CSS styling is heavily used
    for status badges, progress bars, and error displays.
    """
    # Create an ImportSession with various fields populated
    session = baker.make(
        "pbn_import.ImportSession",
        status="running",
        current_step="importing_authors",
        progress_percentage=45,
        error_message="",
    )

    # Get the admin change URL for this session
    url = reverse("admin:pbn_import_importsession_change", args=[session.pk])

    # Try to render the admin detail page with compression enabled
    response = admin_client.get(url)

    # Assert successful render
    assert response.status_code == 200
    assert (
        b"importing_authors" in response.content
        or session.current_step.encode() in response.content
    )
