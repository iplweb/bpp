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


#: Wspólna treść oświadczenia (także dla okresów bez własnego szablonu).
SZABLON_OSWIADCZENIA = "oswiadczenia/tresc_jednego_oswiadczenia.html"


def szablony_oswiadczenia(rok):
    """Szablony treści oświadczenia dla pracy z roku ``rok``, od
    najbardziej szczegółowego: szablon okresu ewaluacji, do którego należy
    praca (``tresc_jednego_oswiadczenia_<rok_od>_<rok_do>.html``; można go
    też nadpisać w bazie — DBTemplates), potem wspólny."""
    okres = okres_domyslny(rok) if rok is not None else None
    if okres is None:
        return [SZABLON_OSWIADCZENIA]
    return [
        f"oswiadczenia/tresc_jednego_oswiadczenia_{okres.rok_od}_{okres.rok_do}.html",
        SZABLON_OSWIADCZENIA,
    ]


@register.filter
def szablon_oswiadczenia(rok):
    """``{% include object.rok|szablon_oswiadczenia with ... %}``."""
    return szablony_oswiadczenia(rok)
