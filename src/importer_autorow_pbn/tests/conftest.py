import pytest
from model_bakery import baker

from importer_autorow_pbn.models import CachedScientistMatch
from pbn_api.models import Scientist


@pytest.fixture
def valid_cache():
    """Create a valid cache entry so the view doesn't redirect to rebuild page."""
    scientist = baker.make(Scientist, from_institution_api=True)
    return CachedScientistMatch.objects.create(scientist=scientist, matched_autor=None)


@pytest.fixture
def create_scientist():
    """Helper to create Scientist objects for testing.

    Also creates a CachedScientistMatch entry to ensure cache validity.
    """

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

        # Create cache entry to ensure cache validity for view tests
        CachedScientistMatch.objects.create(scientist=scientist, matched_autor=None)

        return scientist

    return _create
