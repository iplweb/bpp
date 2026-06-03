"""Testy backendu OIDC (faza 1 — obserwacja claimów).

``BppOIDCBackend.verify_claims`` jest testowany na instancji utworzonej bez
``__init__`` (``object.__new__``), bo bazowy konstruktor ``mozilla-django-oidc``
wymaga kompletu ``OIDC_OP_*``/``OIDC_RP_*`` w ustawieniach. Sama metoda
korzysta tylko ze statycznego ``get_settings`` i loggera, więc to wystarcza.
"""

import logging

from oidc_integration.backends import BppOIDCBackend


def _backend():
    return object.__new__(BppOIDCBackend)


def test_verify_claims_przepuszcza_gdy_jest_email():
    assert _backend().verify_claims({"email": "jan@uafm.edu.pl"}) is True


def test_verify_claims_odrzuca_bez_emaila():
    # Domyślny scope zawiera "email", więc brak claimu email = odmowa.
    assert _backend().verify_claims({"sub": "123"}) is False


def test_verify_claims_loguje_claimy(caplog):
    with caplog.at_level(logging.INFO, logger="oidc_integration.backends"):
        _backend().verify_claims({"email": "jan@uafm.edu.pl", "sub": "123"})
    assert any("otrzymane claimy" in rec.message for rec in caplog.records)
