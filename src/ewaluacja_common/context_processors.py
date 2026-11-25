from django.utils.functional import SimpleLazyObject

from ewaluacja_common.okres import okres_dla_request, pokazac_pasek_okresu
from ewaluacja_common.url_okres import adres_dla_okresu


def _linki_okresow(request):
    """``[(okres, adres)]`` — bieżąca strona w każdym z okresów (pasek);
    bez ręcznie wpisanych lat, żeby dane zgadzały się z wybranym okresem."""
    from ewaluacja_common.models import OkresEwaluacji

    return [
        (okres, adres_dla_okresu(request, okres, bez_lat=True))
        for okres in OkresEwaluacji.objects.all()
    ]


def okres_ewaluacji(request):
    """``okres_ewaluacji`` (wybrany albo domyślny) i ``okresy_ewaluacji`` —
    leniwie, bez zapytań na stronach, które ich nie używają.
    ``pokaz_wybor_okresu`` — czy pokazać pasek wyboru okresu."""
    from ewaluacja_common.models import OkresEwaluacji

    return {
        "okres_ewaluacji": SimpleLazyObject(lambda: okres_dla_request(request)),
        "okresy_ewaluacji": SimpleLazyObject(
            lambda: list(OkresEwaluacji.objects.all())
        ),
        "linki_okresow": SimpleLazyObject(lambda: _linki_okresow(request)),
        "pokaz_wybor_okresu": pokazac_pasek_okresu(
            getattr(request, "resolver_match", None)
        ),
    }
