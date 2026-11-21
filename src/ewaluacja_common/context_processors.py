from django.utils.functional import SimpleLazyObject

from ewaluacja_common.okres import APLIKACJE_Z_OKRESEM, okres_dla_request


def okres_ewaluacji(request):
    """``okres_ewaluacji`` (wybrany albo domyślny) i ``okresy_ewaluacji`` —
    leniwie, bez zapytań na stronach, które ich nie używają.
    ``pokaz_wybor_okresu`` — czy górna belka ma pokazać przełącznik."""
    from ewaluacja_common.models import OkresEwaluacji

    dopasowanie = getattr(request, "resolver_match", None)
    przestrzen = dopasowanie.namespace if dopasowanie else ""
    return {
        "okres_ewaluacji": SimpleLazyObject(lambda: okres_dla_request(request)),
        "okresy_ewaluacji": SimpleLazyObject(
            lambda: list(OkresEwaluacji.objects.all())
        ),
        "pokaz_wybor_okresu": przestrzen.split(":")[0] in APLIKACJE_Z_OKRESEM,
    }
