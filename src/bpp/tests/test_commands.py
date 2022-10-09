import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_rebuild_kolejnosc(wydawnictwo_ciagle_z_dwoma_autorami):
    call_command("rebuild_kolejnosc")
