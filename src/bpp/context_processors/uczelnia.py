import time

from django.core.cache import cache

from bpp.models.struktura import Uczelnia


class NiezdefiniowanaUczelnia:
    pk = None
    nazwa = "[niezdefiniowana uczelnia]"
    nazwa_dopelniacz = "[niezdefiniowanej uczelni]"
    slug = 'niezdefiniowana-uczelnia'


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
