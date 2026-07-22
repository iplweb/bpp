import pytest
from django.test import RequestFactory

from bpp.context_processors.uczelnia import uczelnia


@pytest.mark.django_db
def test_context_processor_dostarcza_lematy(settings):
    from django.core.cache import cache

    cache.delete(b"bpp_uczelnia")
    ctx = uczelnia(RequestFactory().get("/"))
    assert ctx["nazwa_uczelni"] == "uczelnia"
    assert ctx["nazwa_wydzialu"] == "wydział"
    assert ctx["nazwa_jednostki"] == "jednostka"


@pytest.mark.django_db
def test_zapis_rzeczownika_inwaliduje_cache(rzeczowniki):
    from django.core.cache import cache

    from bpp.models import Rzeczownik

    cache.delete(b"bpp_uczelnia")
    uczelnia(RequestFactory().get("/"))  # zasiej cache
    Rzeczownik.objects.filter(uid="JEDNOSTKA").update(m="dział")
    # sam update() nie woła save(); wołamy zapis pełnego obiektu:
    obj = Rzeczownik.objects.get(uid="JEDNOSTKA")
    obj.save()
    ctx = uczelnia(RequestFactory().get("/"))
    assert ctx["nazwa_jednostki"] == "dział"
