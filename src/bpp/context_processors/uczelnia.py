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


def uczelnia(request):
    timeout, value = cache.get(b"bpp_uczelnia", (0, None))

    if value is not None:
        if time.time() < timeout:
            return value

    u = Uczelnia.objects.get_for_request(request)
    if u is None:
        return {"uczelnia": NiezdefiniowanaUczelnia, **_lematy()}

    value = {"uczelnia": u, **_lematy()}
    cache.set(b"bpp_uczelnia", (time.time() + 3600, value))
    return value


@receiver(post_save, sender=Uczelnia)
def invalidate_uczelnia_caches(*args, **kw):
    """Wyczyść cache zależne od ustawień uczelni po jej zapisie.

    Dwie niezależne warstwy trzymają migawkę obiektu ``Uczelnia``:

    * ``b"bpp_uczelnia"`` — cache context processora (górny pasek),
    * ``get_uczelnia_context_data`` — ``@cached`` z cacheops, kontekst
      strony głównej. To cache *funkcji*, więc cacheops NIE czyści go
      automatycznie przy zapisie modelu (robi to tylko dla zapytań ORM) —
      trzeba wołać ``.invalidate()`` ręcznie, analogicznie do sygnałów
      na ``Wydzial``/``Jednostka``/``Article``.

    Import lokalny, żeby uniknąć cyklu context_processors -> views.
    """
    from bpp.views.browse import get_uczelnia_context_data

    cache.delete(b"bpp_uczelnia")
    get_uczelnia_context_data.invalidate()


@receiver(post_save, sender=Rzeczownik)
def invalidate_lematy_cache(*args, **kw):
    """Zmiana nazwy w Rzeczowniku ma natychmiast odświeżyć lematy w kontekście."""
    cache.delete(b"bpp_uczelnia")
