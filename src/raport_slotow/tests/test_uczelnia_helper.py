import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import Uczelnia
from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu


@pytest.fixture
def uczelnia_bazowa(db, uczelnia):
    """Uczelnia podstawowa powiązana z requestem przez _uczelnia."""
    return uczelnia


@pytest.fixture
def druga_uczelnia(db):
    site, _ = Site.objects.get_or_create(
        domain="druga.testserver", defaults={"name": "druga"}
    )
    return Uczelnia.objects.create(
        skrot="DR", nazwa="Druga uczelnia", site=site
    )


def _make_request(uczelnia, user, extra_get=None):
    """Lekki fake request z _uczelnia, user i GET."""

    class FakeRequest:
        GET = {}

    req = FakeRequest()
    req._uczelnia = uczelnia
    req.user = user
    if extra_get:
        req.GET = extra_get
    return req


@pytest.mark.django_db
def test_zwykly_uzytkownik_nie_moze_nadpisac_uczelni(
    uczelnia_bazowa, druga_uczelnia
):
    """Nie-superuser zawsze dostaje uczelnię z requestu mimo ?uczelnia=."""
    zwykly = baker.make("bpp.BppUser", is_superuser=False)
    req = _make_request(
        uczelnia_bazowa, zwykly, extra_get={"uczelnia": str(druga_uczelnia.pk)}
    )

    wynik = uczelnia_dla_odczytu(req)

    assert wynik == uczelnia_bazowa


@pytest.mark.django_db
def test_superuser_moze_nadpisac_uczelnie(uczelnia_bazowa, druga_uczelnia):
    """Superuser z ?uczelnia=<valid pk> dostaje wybraną uczelnię."""
    su = baker.make("bpp.BppUser", is_superuser=True)
    req = _make_request(
        uczelnia_bazowa, su, extra_get={"uczelnia": str(druga_uczelnia.pk)}
    )

    wynik = uczelnia_dla_odczytu(req)

    assert wynik == druga_uczelnia


@pytest.mark.django_db
def test_superuser_niepoprawne_pk_wraca_do_bazowej(uczelnia_bazowa):
    """Superuser z niepoprawną wartością ?uczelnia= dostaje uczelnię bazową."""
    su = baker.make("bpp.BppUser", is_superuser=True)

    for zly_pk in ["99999999", "abc", "", None]:
        get = {"uczelnia": zly_pk} if zly_pk is not None else {}
        req = _make_request(uczelnia_bazowa, su, extra_get=get)
        wynik = uczelnia_dla_odczytu(req)
        assert wynik == uczelnia_bazowa, (
            f"Oczekiwano uczelni bazowej dla ?uczelnia={zly_pk!r}"
        )
