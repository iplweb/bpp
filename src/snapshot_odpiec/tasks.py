from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor


def _policz(przypieta, okres=None):
    """Liczba przypisań z dyscypliną o danym stanie przypięcia; z ``okres`` —
    tylko w pracach z lat okresu ewaluacji."""
    filtr = {}
    if okres is not None:
        filtr = {"rekord__rok__gte": okres.rok_od, "rekord__rok__lte": okres.rok_do}
    return sum(
        model.objects.exclude(dyscyplina_naukowa=None)
        .filter(przypieta=przypieta, **filtr)
        .count()
        # Patenty nie biorą udziału w przypięciach/odpięciach.
        for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor)
    )


def suma_odpietych_dyscyplin(okres=None):
    return _policz(False, okres)


def suma_przypietych_dyscyplin(okres=None):
    return _policz(True, okres)
