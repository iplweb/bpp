import pytest
from django.db import IntegrityError
from model_bakery import baker

from orcid_integration.models import ORCIDIdentity


@pytest.mark.django_db
def test_orcid_identity_unique_issuer_sub():
    """Ta sama para (issuer, ORCID iD) nie może być powiązana dwukrotnie —
    to jest constraint zamykający przejęcie konta."""
    u1 = baker.make("bpp.BppUser")
    u2 = baker.make("bpp.BppUser")
    ORCIDIdentity.objects.create(
        user=u1, issuer="https://orcid.org", sub="0000-0002-1825-0097"
    )
    with pytest.raises(IntegrityError):
        ORCIDIdentity.objects.create(
            user=u2, issuer="https://orcid.org", sub="0000-0002-1825-0097"
        )


@pytest.mark.django_db
def test_orcid_identity_unique_user_per_issuer():
    """Jedno konto = najwyżej jedna tożsamość na dany issuer (środowisko)."""
    u = baker.make("bpp.BppUser")
    ORCIDIdentity.objects.create(
        user=u, issuer="https://orcid.org", sub="0000-0002-1825-0097"
    )
    with pytest.raises(IntegrityError):
        ORCIDIdentity.objects.create(
            user=u, issuer="https://orcid.org", sub="0000-0001-5109-3700"
        )


@pytest.mark.django_db
def test_orcid_identity_sandbox_and_prod_do_not_collide():
    """Ta sama ORCID iD w sandboxie i na produkcji to różne tożsamości —
    issuer je rozróżnia, więc nie ma kolizji unikalności."""
    u1 = baker.make("bpp.BppUser")
    u2 = baker.make("bpp.BppUser")
    ORCIDIdentity.objects.create(
        user=u1, issuer="https://orcid.org", sub="0000-0002-1825-0097"
    )
    ORCIDIdentity.objects.create(
        user=u2, issuer="https://sandbox.orcid.org", sub="0000-0002-1825-0097"
    )
    assert ORCIDIdentity.objects.count() == 2


@pytest.mark.django_db
def test_orcid_identity_reverse_accessor():
    u = baker.make("bpp.BppUser")
    ORCIDIdentity.objects.create(user=u, issuer="https://orcid.org", sub="s")
    assert u.orcid_identities.count() == 1
