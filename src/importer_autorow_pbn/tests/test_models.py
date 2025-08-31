import pytest
from model_bakery import baker

from importer_autorow_pbn.models import DoNotRemind
from pbn_api.models import Scientist


@pytest.mark.django_db
def test_do_not_remind_creation():
    """Test creating a DoNotRemind instance"""
    scientist = baker.make(Scientist)
    user = baker.make("bpp.BppUser")

    do_not_remind = DoNotRemind.objects.create(
        scientist=scientist, ignored_by=user, reason="Test reason"
    )

    assert do_not_remind.scientist == scientist
    assert do_not_remind.ignored_by == user
    assert do_not_remind.reason == "Test reason"
    assert do_not_remind.ignored_at is not None


@pytest.mark.django_db
def test_do_not_remind_str():
    """Test string representation of DoNotRemind"""
    scientist = baker.make(Scientist, lastName="Kowalski", name="Jan")
    do_not_remind = baker.make(DoNotRemind, scientist=scientist)

    str_repr = str(do_not_remind)
    assert "Kowalski" in str_repr or str(scientist.mongoId) in str_repr
    assert "ignorowany" in str_repr


@pytest.mark.django_db
def test_do_not_remind_unique_scientist():
    """Test that each scientist can only be in DoNotRemind once"""
    scientist = baker.make(Scientist)
    baker.make(DoNotRemind, scientist=scientist)

    # Try to create another DoNotRemind for the same scientist
    with pytest.raises(Exception):  # Should raise IntegrityError
        DoNotRemind.objects.create(scientist=scientist)


@pytest.mark.django_db
def test_do_not_remind_cascade_delete():
    """Test that DoNotRemind is deleted when Scientist is deleted"""
    scientist = baker.make(Scientist)
    do_not_remind = baker.make(DoNotRemind, scientist=scientist)

    assert DoNotRemind.objects.filter(pk=do_not_remind.pk).exists()

    scientist.delete()

    assert not DoNotRemind.objects.filter(pk=do_not_remind.pk).exists()
