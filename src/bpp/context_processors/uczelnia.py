import time

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

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


@receiver(post_save, sender=Uczelnia)
def invalidate_uczelnia_caches(sender, instance, **kw):
    """Wyczyść cache zależne od ustawień uczelni po jej zapisie.

    Dwie niezależne warstwy trzymają migawkę obiektu ``Uczelnia``:

    * cache context processora (górny pasek) — kluczowany per-site
      (``bpp_uczelnia_{site_pk}``), plus legacy klucz ``b"bpp_uczelnia"``,
    * ``get_uczelnia_context_data`` — ``@cached`` z cacheops, kontekst
      strony głównej. To cache *funkcji*, więc cacheops NIE czyści go
      automatycznie przy zapisie modelu (robi to tylko dla zapytań ORM) —
      trzeba wołać ``.invalidate()`` ręcznie, analogicznie do sygnałów
      na ``Wydzial``/``Jednostka``/``Article``.

    Import lokalny, żeby uniknąć cyklu context_processors -> views.
    """
    from bpp.views.browse import get_uczelnia_context_data

    site = getattr(instance, "site", None)
    site_pk = getattr(site, "pk", 0)
    cache.delete(f"bpp_uczelnia_{site_pk}")
    # Legacy klucz (sprzed kluczowania per-site) — backward compatibility.
    cache.delete(b"bpp_uczelnia")
    get_uczelnia_context_data.invalidate()


@receiver(post_save, sender=Rzeczownik)
def invalidate_lematy_cache(*args, **kw):
    """Zmiana nazwy w Rzeczowniku odświeża lematy w kontekście.

    Lematy są globalne (tabela ``Rzeczownik``), ale trafiają do cache'u
    context processora kluczowanego per-site (``bpp_uczelnia_{site_pk}``),
    więc trzeba wyczyścić klucze wszystkich site'ów (plus brak-site i legacy).
    """
    from django.contrib.sites.models import Site

    cache.delete(b"bpp_uczelnia")  # legacy (sprzed kluczowania per-site)
    cache.delete("bpp_uczelnia_0")  # brak request.site (single-host)
    for site_pk in Site.objects.values_list("pk", flat=True):
        cache.delete(f"bpp_uczelnia_{site_pk}")
