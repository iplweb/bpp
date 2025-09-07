from bpp.models import Patent_Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor


def suma_odpietych_dyscyplin():
    return (
        Wydawnictwo_Ciagle_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=True)
        .count()
        + Wydawnictwo_Zwarte_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=True)
        .count()
        + Patent_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=True)
        .count()
    )


def suma_przypietych_dyscyplin():
    return (
        Wydawnictwo_Ciagle_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=False)
        .count()
        + Wydawnictwo_Zwarte_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=False)
        .count()
        + Patent_Autor.objects.exclude(dyscyplina_naukowa=None)
        .exclude(przypieta=False)
        .count()
    )
