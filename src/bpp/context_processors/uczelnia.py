from bpp.models.struktura import Uczelnia


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