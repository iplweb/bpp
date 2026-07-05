"""Rozstrzyganie 'uczelni oglądającego' dla odczytów slotowych (read-side).

Hybryda: domyślnie uczelnia z requestu (site/domena); superuser może nadpisać
jawnym parametrem ``?uczelnia=<pk>``.
"""

from bpp.models import Uczelnia


def uczelnia_dla_odczytu(request):
    bazowa = Uczelnia.objects.get_for_request(request)

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_superuser:
        pk = request.GET.get("uczelnia")
        if pk:
            try:
                return Uczelnia.objects.get(pk=pk)
            except (Uczelnia.DoesNotExist, ValueError, TypeError):
                return bazowa
    return bazowa
