"""Tests for komparator_pbn_udzialy application."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle_Autor
from komparator_pbn_udzialy.models import RozbieznoscDyscyplinPBN
from pbn_api.models import OswiadczenieInstytucji


@pytest.fixture
def wydawnictwo_ciagle_autor_fixture(autor_jan_kowalski, jednostka, wydawnictwo_ciagle):
    """Create a Wydawnictwo_Ciagle_Autor for testing."""
    return baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo_ciagle,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        kolejnosc=0,
    )


@pytest.fixture
def oswiadczenie_fixture():
    """Create an OswiadczenieInstytucji for testing."""
    return baker.make(OswiadczenieInstytucji)


@pytest.mark.django_db
def test_rozbieznosc_dyscyplin_pbn_creation(
    wydawnictwo_ciagle_autor_fixture, oswiadczenie_fixture, dyscyplina1
):
    """Test creating RozbieznoscDyscyplinPBN model."""
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor)

    rozbieznosc = RozbieznoscDyscyplinPBN.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle_autor_fixture.pk,
        oswiadczenie_instytucji=oswiadczenie_fixture,
        dyscyplina_bpp=dyscyplina1,
        dyscyplina_pbn=None,
    )

    assert rozbieznosc.pk is not None
    assert rozbieznosc.dyscypliny_rozne is True


@pytest.mark.django_db
def test_rozbieznosc_dyscyplin_pbn_str(
    wydawnictwo_ciagle_autor_fixture, oswiadczenie_fixture
):
    """Test string representation of RozbieznoscDyscyplinPBN."""
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor)

    rozbieznosc = RozbieznoscDyscyplinPBN.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle_autor_fixture.pk,
        oswiadczenie_instytucji=oswiadczenie_fixture,
    )

    str_repr = str(rozbieznosc)
    assert "Rozbieżność" in str_repr


@pytest.mark.django_db
def test_rozbieznosc_dyscyplin_pbn_dyscypliny_rozne_both_none(
    wydawnictwo_ciagle_autor_fixture, oswiadczenie_fixture
):
    """Test dyscypliny_rozne returns False when both are None."""
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor)

    rozbieznosc = RozbieznoscDyscyplinPBN.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle_autor_fixture.pk,
        oswiadczenie_instytucji=oswiadczenie_fixture,
        dyscyplina_bpp=None,
        dyscyplina_pbn=None,
    )

    assert rozbieznosc.dyscypliny_rozne is False


@pytest.mark.django_db
def test_rozbieznosc_dyscyplin_pbn_dyscypliny_rozne_same(
    wydawnictwo_ciagle_autor_fixture, oswiadczenie_fixture, dyscyplina1
):
    """Test dyscypliny_rozne returns False when both are same."""
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor)

    rozbieznosc = RozbieznoscDyscyplinPBN.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle_autor_fixture.pk,
        oswiadczenie_instytucji=oswiadczenie_fixture,
        dyscyplina_bpp=dyscyplina1,
        dyscyplina_pbn=dyscyplina1,
    )

    assert rozbieznosc.dyscypliny_rozne is False


@pytest.mark.django_db
def test_rozbieznosc_get_autor(
    wydawnictwo_ciagle_autor_fixture, oswiadczenie_fixture, autor_jan_kowalski
):
    """Test get_autor method returns correct author."""
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor)

    rozbieznosc = RozbieznoscDyscyplinPBN.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle_autor_fixture.pk,
        oswiadczenie_instytucji=oswiadczenie_fixture,
    )

    assert rozbieznosc.get_autor() == autor_jan_kowalski


@pytest.mark.django_db
def test_rozbieznosc_get_publikacja(
    wydawnictwo_ciagle_autor_fixture, oswiadczenie_fixture, wydawnictwo_ciagle
):
    """Test get_publikacja method returns correct publication."""
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor)

    rozbieznosc = RozbieznoscDyscyplinPBN.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle_autor_fixture.pk,
        oswiadczenie_instytucji=oswiadczenie_fixture,
    )

    assert rozbieznosc.get_publikacja() == wydawnictwo_ciagle


# Tests for KomparatorDyscyplinPBN utility class


@pytest.mark.django_db
def test_komparator_dyscyplin_init():
    """Test KomparatorDyscyplinPBN initialization."""
    from komparator_pbn_udzialy.utils import KomparatorDyscyplinPBN

    komparator = KomparatorDyscyplinPBN(clear_existing=True, show_progress=False)

    assert komparator.clear_existing is True
    assert komparator.show_progress is False
    assert komparator.stats["processed"] == 0


@pytest.mark.django_db
def test_komparator_clear_discrepancies(
    wydawnictwo_ciagle_autor_fixture, oswiadczenie_fixture
):
    """Test clear_discrepancies removes existing records."""
    from komparator_pbn_udzialy.utils import KomparatorDyscyplinPBN

    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor)

    # Create a discrepancy
    RozbieznoscDyscyplinPBN.objects.create(
        content_type=ct,
        object_id=wydawnictwo_ciagle_autor_fixture.pk,
        oswiadczenie_instytucji=oswiadczenie_fixture,
    )

    assert RozbieznoscDyscyplinPBN.objects.count() == 1

    komparator = KomparatorDyscyplinPBN(show_progress=False)
    count = komparator.clear_discrepancies()

    assert count == 1
    assert RozbieznoscDyscyplinPBN.objects.count() == 0


# Tests for Celery tasks


@pytest.mark.django_db
def test_porownaj_dyscypliny_pbn_task_success():
    """Test that porownaj_dyscypliny_pbn_task executes successfully."""
    from komparator_pbn_udzialy.tasks import porownaj_dyscypliny_pbn_task

    with patch("komparator_pbn_udzialy.tasks.cache"):
        with patch(
            "komparator_pbn_udzialy.tasks.KomparatorDyscyplinPBN"
        ) as mock_komparator:
            mock_instance = MagicMock()
            mock_instance.stats = {"processed": 10, "discrepancies_found": 2}
            mock_instance.run.return_value = mock_instance.stats
            mock_komparator.return_value = mock_instance

            result = porownaj_dyscypliny_pbn_task.apply(args=(False,)).result

            assert result["status"] == "SUCCESS"
            assert "stats" in result


@pytest.mark.django_db
def test_porownaj_dyscypliny_pbn_task_progress_tracking():
    """Test that porownaj_dyscypliny_pbn_task updates progress via cache."""
    from komparator_pbn_udzialy.tasks import porownaj_dyscypliny_pbn_task

    cache_calls = []

    def track_cache_set(key, value, timeout):
        cache_calls.append({"key": key, "value": value})

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.set.side_effect = track_cache_set

        with patch(
            "komparator_pbn_udzialy.tasks.KomparatorDyscyplinPBN"
        ) as mock_komparator:
            mock_instance = MagicMock()
            mock_instance.stats = {"processed": 0, "discrepancies_found": 0}
            mock_instance.run.return_value = mock_instance.stats
            mock_komparator.return_value = mock_instance

            porownaj_dyscypliny_pbn_task.apply(args=(False,))

    # Cache should have been called at least for init and success
    assert len(cache_calls) >= 2


@pytest.mark.django_db
def test_get_task_status_pending():
    """Test get_task_status returns pending for unknown task."""
    from komparator_pbn_udzialy.tasks import get_task_status

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("komparator_pbn_udzialy.tasks.AsyncResult") as mock_result:
            mock_task = MagicMock()
            mock_task.state = "PENDING"
            mock_result.return_value = mock_task

            status = get_task_status("fake-task-id")

    assert status["status"] == "PENDING"


@pytest.mark.django_db
def test_get_task_status_from_cache():
    """Test get_task_status returns cached status."""
    from komparator_pbn_udzialy.tasks import get_task_status

    cached_status = {
        "status": "PROGRESS",
        "current": 5,
        "total": 10,
        "stats": {"processed": 5},
    }

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = cached_status

        status = get_task_status("cached-task-id")

    assert status == cached_status


@pytest.mark.django_db
def test_get_task_status_success():
    """Test get_task_status returns success state."""
    from komparator_pbn_udzialy.tasks import get_task_status

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("komparator_pbn_udzialy.tasks.AsyncResult") as mock_result:
            mock_task = MagicMock()
            mock_task.state = "SUCCESS"
            mock_task.info = {"message": "Done", "stats": {"processed": 100}}
            mock_result.return_value = mock_task

            status = get_task_status("success-task-id")

    assert status["status"] == "SUCCESS"


@pytest.mark.django_db
def test_get_task_status_failure():
    """Test get_task_status returns failure state."""
    from komparator_pbn_udzialy.tasks import get_task_status

    with patch("komparator_pbn_udzialy.tasks.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("komparator_pbn_udzialy.tasks.AsyncResult") as mock_result:
            mock_task = MagicMock()
            mock_task.state = "FAILURE"
            mock_task.info = "Error message"
            mock_result.return_value = mock_task

            status = get_task_status("failure-task-id")

    assert status["status"] == "FAILURE"
