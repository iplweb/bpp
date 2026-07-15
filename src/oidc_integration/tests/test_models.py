import pytest
from django.db import IntegrityError
from model_bakery import baker

from oidc_integration.models import OIDCIdentity


@pytest.mark.django_db
def test_oidc_identity_unique_issuer_sub():
    u1 = baker.make("bpp.BppUser")
    u2 = baker.make("bpp.BppUser")
    OIDCIdentity.objects.create(user=u1, issuer="https://kc/realms/x", sub="a")
    with pytest.raises(IntegrityError):
        OIDCIdentity.objects.create(user=u2, issuer="https://kc/realms/x", sub="a")


@pytest.mark.django_db
def test_oidc_identity_reverse_accessor():
    u = baker.make("bpp.BppUser")
    OIDCIdentity.objects.create(user=u, issuer="iss", sub="s")
    assert u.oidc_identities.count() == 1
