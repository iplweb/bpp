from django import template

from ewaluacja_common.okres import okres_domyslny

register = template.Library()


@register.filter
def lata_ewaluacji(rok):
    """Lata okresu ewaluacji, do którego należy praca z roku ``rok``, np.
    ``2022-2025`` — w treści oświadczenia („za lata ...”). Okres wynika z roku
    pracy, a NIE z okresu wybranego przez użytkownika na pasku."""
    if rok is None:
        return ""
    okres = okres_domyslny(rok)
    if okres is None:
        return ""
    return f"{okres.rok_od}-{okres.rok_do}"
