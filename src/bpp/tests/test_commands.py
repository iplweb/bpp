import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_rebuild_kolejnosc(wydawnictwo_ciagle_z_dwoma_autorami):
    call_command("rebuild_kolejnosc")


@pytest.mark.django_db
def test_migrate():
    call_command("migrate")


@pytest.mark.django_db
@pytest.mark.vcr
def test_importuj_liste_ministerialna_2023():
    call_command("import_lista_ministerialna_2023", "--download")
