from bpp.models.struktura import Uczelnia
from bpp.system import greek, cyrylic, iso



class NiezdefiniowanaUczelnia:
    pk = None
    nazwa = "[niezdefiniowana uczelnia]"
    nazwa_dopelniacz = "[niezdefiniowanej uczelni]"
    slug = 'niezdefiniowana-uczelnia'


def uczelnia(request):
    try:
        return {'uczelnia': Uczelnia.objects.all()[0]}
    except IndexError:
        return {'uczelnia': NiezdefiniowanaUczelnia}