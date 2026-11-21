"""The ADMINS default is public (e.g. CERIF Identify), so it must be a placeholder."""

from email.utils import getaddresses

from django_bpp.settings import base


def test_domyslny_admins_to_zaslepka():
    domyslny = base.env.scheme["ADMINS"][1]
    ((_nazwa, adres),) = getaddresses([domyslny])
    assert adres.endswith(".invalid")
