import time

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from bpp.cache_strony_glownej import uniewaznij_strone_glowna
from bpp.models.rzeczownik import Rzeczownik
from bpp.models.struktura import Uczelnia
from bpp.nazwy import lemat


class NiezdefiniowanaUczelnia:
    pk = None
    nazwa = "[niezdefiniowana uczelnia]"
    nazwa_dopelniacz = "[niezdefiniowanej uczelni]"
    slug = "niezdefiniowana-uczelnia"
    podpowiadaj_dyscypliny = False
    skrot = "NdU"

    def __getattr__(self, item):
        if item.startswith("pokazuj_"):
            return False
        return super().__getattr__(item)

    def sprawdz_uprawnienie(self, *args, **kw):
        return False


def _lematy():
    return {
        "nazwa_uczelni": lemat("UCZELNIA"),
        "nazwa_wydzialu": lemat("WYDZIAL"),
        "nazwa_jednostki": lemat("JEDNOSTKA"),
    }


def _cache_key_for_request(request):
    site = getattr(request, "site", None)
    site_pk = getattr(site, "pk", 0)
    return f"bpp_uczelnia_{site_pk}"


def uczelnia(request):
    cache_key = _cache_key_for_request(request)
    timeout, value = cache.get(cache_key, (0, None))

    if value is not None:
        if time.time() < timeout:
            return value

    u = Uczelnia.objects.get_for_request(request)
    if u is None:
        return {"uczelnia": NiezdefiniowanaUczelnia, **_lematy()}

    value = {"uczelnia": u, **_lematy()}
    cache.set(cache_key, (time.time() + 3600, value))
    return value


def _wyczysc_cache_kontekstu():
    """Usuń zapamiętany kontekst top-bara dla WSZYSTKICH site'ów.

    Klucz przy odczycie pochodzi z ``request.site`` (host → ``Site``, potem
    ``SITE_ID``), a NIE z ``uczelnia.site``. Gdy strona jest oglądana pod
    domeną, której ``Site`` nie ma przypiętej uczelni, middleware i tak
    podstawia „jedyną uczelnię" — wtedy obiekt ``Uczelnia`` siedzi pod
    kluczem cudzego site'u i kasowanie samego ``bpp_uczelnia_{instance.site}``
    go nie dosięga (stara wartość żyje do TTL, 1h). Site'ów jest kilka-
    kilkanaście, więc czyścimy wszystkie, plus brak-site i legacy.
    """
    from django.contrib.sites.models import Site

    cache.delete(b"bpp_uczelnia")  # legacy (sprzed kluczowania per-site)
    cache.delete("bpp_uczelnia_0")  # brak request.site (single-host)
    for site_pk in Site.objects.values_list("pk", flat=True):
        cache.delete(f"bpp_uczelnia_{site_pk}")


@receiver(post_save, sender=Uczelnia)
def invalidate_uczelnia_caches(sender, instance, **kw):
    """Wyczyść cache zależne od ustawień uczelni po jej zapisie.

    Dwie niezależne warstwy trzymają migawkę obiektu ``Uczelnia``:

    * cache context processora (górny pasek) — kluczowany per-site
      (``bpp_uczelnia_{site_pk}``), patrz ``_wyczysc_cache_kontekstu``,
    * ``get_uczelnia_context_data`` — ``@cached`` z cacheops, kontekst
      strony głównej (także jej top-bara: kontekst widoku nadpisuje ten
      z context processora). Unieważniany zmianą generacji — patrz
      ``bpp.cache_strony_glownej``.
    """
    _wyczysc_cache_kontekstu()
    uniewaznij_strone_glowna()


@receiver(post_save, sender=Rzeczownik)
def invalidate_lematy_cache(*args, **kw):
    """Zmiana nazwy w Rzeczowniku odświeża lematy w kontekście.

    Lematy są globalne (tabela ``Rzeczownik``), ale trafiają do cache'u
    context processora kluczowanego per-site, więc czyścimy wszystkie.
    """
    _wyczysc_cache_kontekstu()
