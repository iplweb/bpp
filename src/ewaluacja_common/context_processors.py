from django.utils.functional import SimpleLazyObject

from ewaluacja_common.okres import okres_dla_request, pokazac_pasek_okresu


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
        "pokaz_wybor_okresu": pokazac_pasek_okresu(
            getattr(request, "resolver_match", None)
        ),
    }
