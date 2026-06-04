import pytest
from cryptography.fernet import Fernet
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_uczelnia_dspace_password_encrypted(fernet_key):
    from bpp.models import Uczelnia

    u = baker.make(Uczelnia)
    u.dspace_api_password = "sekret"
    u.save()

    from django.db import connection

    with connection.cursor() as c:
        c.execute(
            "SELECT dspace_api_password FROM bpp_uczelnia WHERE id=%s", [u.id]
        )
        raw = c.fetchone()[0]
    assert raw != "sekret"

    assert Uczelnia.objects.get(pk=u.pk).dspace_api_password == "sekret"


@pytest.mark.django_db
def test_uczelnia_dspace_defaults(fernet_key):
    from bpp.models import Uczelnia

    u = baker.make(Uczelnia)
    assert u.dspace_aktywny is False
    assert u.dspace_api_endpoint == ""
