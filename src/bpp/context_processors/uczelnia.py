import time

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from bpp.models.struktura import Uczelnia


class NiezdefiniowanaUczelnia:
    pk = None
    nazwa = "[niezdefiniowana uczelnia]"
    nazwa_dopelniacz = "[niezdefiniowanej uczelni]"
    slug = 'niezdefiniowana-uczelnia'
    podpowiadaj_dyscypliny = False


BRAK_UCZELNI = {'uczelnia': NiezdefiniowanaUczelnia}

def uczelnia(request):
    timeout, value = cache.get(b"bpp_uczelnia", (0, None))

    if value is not None:
        if time.time() < timeout:
            return value

    u = Uczelnia.objects.first()
    if u is None:
        return BRAK_UCZELNI

    value = {'uczelnia': u}
    cache.set(b"bpp_uczelnia", (time.time() + 3600, value))
    return value


@receiver(post_save, sender=Uczelnia)
def remove_cache_key(*args, **kw):
    cache.delete(b"bpp_uczelnia")
