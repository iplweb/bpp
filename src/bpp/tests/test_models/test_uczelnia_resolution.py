"""Multi-hosted: rozstrzyganie uczelni bez „uczelni domyślnej".

Pokrywa ``UczelniaManager``: ``get_single_uczelnia_or_none`` /
``get_single_uczelnia_or_fail`` / ``get_for_site`` / ``get_for_request``.
Zasada: brak → None, jedna → ta, wiele bez wskazania z site → None
(NIGDY pierwsza-z-brzegu). ``get_for_request`` NIGDY nie rzuca.
"""

import pytest
from django.test import RequestFactory
from model_bakery import baker

from bpp.models import Uczelnia


@pytest.mark.django_db
def test_get_single_uczelnia_or_none_pusta_baza():
    assert Uczelnia.objects.get_single_uczelnia_or_none() is None


@pytest.mark.django_db
def test_get_single_uczelnia_or_none_jedna():
    u = baker.make(Uczelnia)
    assert Uczelnia.objects.get_single_uczelnia_or_none() == u


@pytest.mark.django_db
def test_get_single_uczelnia_or_none_wiele_to_none():
    baker.make(Uczelnia)
    baker.make(Uczelnia)
    assert Uczelnia.objects.get_single_uczelnia_or_none() is None


@pytest.mark.django_db
def test_get_single_uczelnia_or_fail_jedna():
    u = baker.make(Uczelnia)
    assert Uczelnia.objects.get_single_uczelnia_or_fail() == u


@pytest.mark.django_db
def test_get_single_uczelnia_or_fail_wiele_rzuca():
    baker.make(Uczelnia)
    baker.make(Uczelnia)
    with pytest.raises(Uczelnia.MultipleObjectsReturned):
        Uczelnia.objects.get_single_uczelnia_or_fail()


@pytest.mark.django_db
def test_get_single_uczelnia_or_fail_pusta_rzuca():
    with pytest.raises(Uczelnia.DoesNotExist):
        Uczelnia.objects.get_single_uczelnia_or_fail()


@pytest.mark.django_db
def test_get_for_site_none_to_none():
    assert Uczelnia.objects.get_for_site(None) is None


@pytest.mark.django_db
def test_get_for_site_zwraca_uczelnie_site():
    u = baker.make(Uczelnia)
    assert Uczelnia.objects.get_for_site(u.site) == u


@pytest.mark.django_db
def test_get_for_request_cache_zwraca_scacheowana():
    # request._uczelnia ustawione (przez middleware) → bierzemy je, bez DB.
    rf = RequestFactory()
    req = rf.get("/")
    sentinel = object()
    req._uczelnia = sentinel
    assert Uczelnia.objects.get_for_request(req) is sentinel


@pytest.mark.django_db
def test_get_for_request_po_domenie_site(settings):
    settings.ALLOWED_HOSTS = ["*"]
    u = baker.make(Uczelnia)
    u.site.domain = "uczelnia-a.example.com"
    u.site.save()
    rf = RequestFactory()
    req = rf.get("/", HTTP_HOST="uczelnia-a.example.com")
    assert Uczelnia.objects.get_for_request(req) == u
    # i scacheowane
    assert req._uczelnia == u


@pytest.mark.django_db
def test_get_for_request_jedyna_uczelnia_bez_dopasowania_domeny(settings):
    settings.ALLOWED_HOSTS = ["*"]
    u = baker.make(Uczelnia)
    rf = RequestFactory()
    req = rf.get("/", HTTP_HOST="niezmapowana-domena.example")
    # Brak Site dla domeny, ale JEDNA uczelnia → ona.
    assert Uczelnia.objects.get_for_request(req) == u


@pytest.mark.django_db
def test_get_for_request_wiele_uczelni_bez_domeny_to_none_nie_rzuca(settings):
    settings.ALLOWED_HOSTS = ["*"]
    baker.make(Uczelnia)
    baker.make(Uczelnia)
    rf = RequestFactory()
    req = rf.get("/", HTTP_HOST="niezmapowana-domena.example")
    # Wiele uczelni, brak wskazania z domeny → None (ŻADNA), bez wyjątku.
    assert Uczelnia.objects.get_for_request(req) is None


@pytest.mark.django_db
def test_get_for_request_pusta_baza_to_none_nie_rzuca(settings):
    # Setup wizard / pusta baza: strona MUSI działać bez uczelni.
    settings.ALLOWED_HOSTS = ["*"]
    rf = RequestFactory()
    req = rf.get("/", HTTP_HOST="cokolwiek.example")
    assert Uczelnia.objects.get_for_request(req) is None


@pytest.mark.django_db
def test_get_for_request_none_jedna_uczelnia():
    # Wołający z warstwy modelu/CBV bez requestu przekazuje None — nie crash.
    u = baker.make(Uczelnia)
    assert Uczelnia.objects.get_for_request(None) == u


@pytest.mark.django_db
def test_get_for_request_none_wiele_uczelni_to_none_nie_rzuca():
    baker.make(Uczelnia)
    baker.make(Uczelnia)
    assert Uczelnia.objects.get_for_request(None) is None


def test_get_default_nie_istnieje():
    # „Uczelnia domyślna" została usunięta na trwałe.
    assert not hasattr(Uczelnia.objects, "get_default")
    assert "default" not in type(Uczelnia.objects).__dict__
