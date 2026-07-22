import json

from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.filter(name="pretty_json")
def pretty_json(value):
    """Formatuj wartość jako czytelny JSON string."""
    try:
        return json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError):
        return str(value)


@register.filter(name="admin_change_url")
def admin_change_url(obj):
    """Zwróć URL strony edycji obiektu w module redagowania (admin).

    Działa dla dowolnego modelu — nazwa route'u budowana jest z
    ``app_label``/``model_name`` samego obiektu, więc jedno wywołanie
    obsługuje np. i ``Wydawnictwo_Ciagle``, i ``Wydawnictwo_Zwarte``.
    Gdy obiekt nie ma pk albo nie jest zarejestrowany w adminie —
    zwraca pusty string (link się nie pojawi).
    """
    if obj is None or getattr(obj, "pk", None) is None:
        return ""
    meta = obj._meta
    try:
        return reverse(
            f"admin:{meta.app_label}_{meta.model_name}_change",
            args=(obj.pk,),
        )
    except NoReverseMatch:
        return ""
