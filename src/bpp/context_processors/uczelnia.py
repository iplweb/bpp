import time

from bpp.models.struktura import Uczelnia


class NiezdefiniowanaUczelnia:
    pk = None
    nazwa = "[niezdefiniowana uczelnia]"
    nazwa_dopelniacz = "[niezdefiniowanej uczelni]"
    slug = 'niezdefiniowana-uczelnia'


from django.core.cache import cache

def uczelnia(request):
    timeout, value = cache.get("bpp_uczelnia", (0, None))
    t = time.time()

    if t < timeout:
        return value

    try:
        value = {'uczelnia': Uczelnia.objects.first()}
    except IndexError:
        value = {'uczelnia': NiezdefiniowanaUczelnia}

    cache.set("bpp_uczelnia", (t + 3600, value))
    return value
