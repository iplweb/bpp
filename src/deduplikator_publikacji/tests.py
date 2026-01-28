import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from deduplikator_publikacji.models import (
    PublicationDuplicateCandidate,
    PublicationDuplicateScanRun,
)


@pytest.mark.django_db
def test_publication_duplicate_scan_run_creation():
    """Test creating a scan run instance."""
    scan_run = baker.make(
        PublicationDuplicateScanRun,
        year_from=2022,
        year_to=2025,
        status=PublicationDuplicateScanRun.Status.PENDING,
    )
    assert scan_run.pk is not None
    assert scan_run.year_from == 2022
    assert scan_run.year_to == 2025
    assert scan_run.progress_percent == 0


@pytest.mark.django_db
def test_publication_duplicate_scan_run_progress_percent():
    """Test progress percentage calculation."""
    scan_run = baker.make(
        PublicationDuplicateScanRun,
        total_publications_to_scan=100,
        publications_scanned=50,
    )
    assert scan_run.progress_percent == 50.0


@pytest.mark.django_db
def test_publication_duplicate_scan_run_progress_percent_zero_total():
    """Test progress percentage when total is zero."""
    scan_run = baker.make(
        PublicationDuplicateScanRun,
        total_publications_to_scan=0,
        publications_scanned=0,
    )
    assert scan_run.progress_percent == 0


@pytest.mark.django_db
def test_publication_duplicate_candidate_creation(wydawnictwo_ciagle):
    """Test creating a duplicate candidate."""
    scan_run = baker.make(PublicationDuplicateScanRun)
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)

    candidate = PublicationDuplicateCandidate.objects.create(
        scan_run=scan_run,
        original_content_type=ct,
        original_object_id=wydawnictwo_ciagle.pk,
        duplicate_content_type=ct,
        duplicate_object_id=wydawnictwo_ciagle.pk,
        similarity_score=0.95,
        match_reasons=["DOI", "tytuł"],
        original_title="Test Title Original",
        duplicate_title="Test Title Duplicate",
        original_year=2023,
        duplicate_year=2023,
        original_type="wydawnictwo_ciagle",
        duplicate_type="wydawnictwo_ciagle",
    )
    assert candidate.pk is not None
    assert candidate.similarity_score == 0.95
    assert "DOI" in candidate.match_reasons


@pytest.mark.django_db
def test_duplicate_publications_view_requires_login(client):
    """Test that the view requires login."""
    url = reverse("deduplikator_publikacji:duplicate_publications")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_duplicate_publications_view_requires_group(admin_client):
    """Test that the view requires group membership."""
    # admin_user is superuser so should have access
    url = reverse("deduplikator_publikacji:duplicate_publications")
    response = admin_client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_scan_status_view(admin_client):
    """Test the scan status JSON endpoint."""
    scan_run = baker.make(
        PublicationDuplicateScanRun,
        status=PublicationDuplicateScanRun.Status.RUNNING,
        total_publications_to_scan=100,
        publications_scanned=25,
        duplicates_found=5,
    )
    url = reverse(
        "deduplikator_publikacji:scan_status",
        kwargs={"scan_id": scan_run.pk},
    )
    response = admin_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["progress_percent"] == 25.0
    assert data["publications_scanned"] == 25
    assert data["duplicates_found"] == 5
    assert data["finished"] is False


@pytest.mark.django_db
def test_scan_status_view_not_found(admin_client):
    """Test scan status view returns 404 for non-existent scan."""
    url = reverse(
        "deduplikator_publikacji:scan_status",
        kwargs={"scan_id": 99999},
    )
    response = admin_client.get(url)
    assert response.status_code == 404
