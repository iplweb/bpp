import pytest

from pbn_api.models import Scientist


@pytest.fixture
def create_scientist():
    """Helper to create Scientist objects for testing"""

    def _create(mongoId, lastName=None, name=None, **kwargs):
        # Create with minimal required fields
        scientist = Scientist.objects.create(
            mongoId=mongoId,
            from_institution_api=kwargs.pop("from_institution_api", True),
            versions=kwargs.pop("versions", {}),
        )
        # Use update to bypass the save method with pull_up_on_save
        if lastName or name:
            Scientist.objects.filter(mongoId=mongoId).update(
                lastName=lastName, name=name
            )
            scientist.refresh_from_db()
        return scientist

    return _create
