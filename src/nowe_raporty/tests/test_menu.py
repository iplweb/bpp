import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory
from model_bakery import baker

from nowe_raporty.menu import CACHE_KEY, raporty_menu, widoczne_raporty
from nowe_raporty.models import DefinicjaRaportu


def _req(user):
    r = RequestFactory().get("/")
    r.user = user
    return r


def _definicja(slug, **kw):
    kw.setdefault("poziom", DefinicjaRaportu.POZIOM_AUTOR)
    kw.setdefault("poziom_dostepu", DefinicjaRaportu.DOSTEP_WSZYSCY)
    kw.setdefault("aktywny", True)
    return baker.make(DefinicjaRaportu, slug=slug, **kw)


@pytest.mark.django_db
def test_menu_filtruje_widocznosc():
    _definicja("widoczny", kolejnosc=0)
    _definicja("nieaktywny", aktywny=False, kolejnosc=1)
    _definicja(
        "zalogowani",
        poziom_dostepu=DefinicjaRaportu.DOSTEP_ZALOGOWANI,
        kolejnosc=2,
    )
    cache.delete(CACHE_KEY)

    slugi = [d.slug for d in widoczne_raporty(_req(AnonymousUser()))]
    assert slugi == ["widoczny"]


@pytest.mark.django_db
def test_menu_kolejnosc():
    _definicja("b", kolejnosc=5, nazwa="B")
    _definicja("a", kolejnosc=1, nazwa="A")
    cache.delete(CACHE_KEY)

    slugi = [d.slug for d in widoczne_raporty(_req(AnonymousUser()))]
    assert slugi == ["a", "b"]


@pytest.mark.django_db
def test_menu_cache_inwalidacja_na_zapis():
    cache.delete(CACHE_KEY)
    assert widoczne_raporty(_req(AnonymousUser())) == []

    # zapis nowej definicji musi wyczyscic cache (signal post_save)
    _definicja("nowy")

    slugi = [d.slug for d in widoczne_raporty(_req(AnonymousUser()))]
    assert slugi == ["nowy"]


@pytest.mark.django_db
def test_context_processor_zwraca_liste():
    _definicja("x")
    cache.delete(CACHE_KEY)
    out = raporty_menu(_req(AnonymousUser()))
    assert "raporty_menu" in out
    assert [d.slug for d in out["raporty_menu"]] == ["x"]
