import time

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from bpp.models.struktura import Uczelnia


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


BRAK_UCZELNI = {
    "uczelnia": NiezdefiniowanaUczelnia,
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
        return BRAK_UCZELNI

    value = {"uczelnia": u}
    cache.set(cache_key, (time.time() + 3600, value))
    return value


@receiver(post_save, sender=Uczelnia)
def remove_cache_key(sender, instance, **kw):
    """Invalidate uczelnia cache for the site linked to the saved instance."""
    site = getattr(instance, "site", None)
    site_pk = getattr(site, "pk", 0)
    cache.delete(f"bpp_uczelnia_{site_pk}")
    # Also delete the legacy key for backward compatibility
    cache.delete(b"bpp_uczelnia")
