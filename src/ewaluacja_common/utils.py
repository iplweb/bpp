from django.db.models import F, Transform

from ewaluacja2021 import const

from bpp.const import RODZAJ_PBN_ARTYKUL


class NieArtykul(Transform):

    template = f"(%(expressions)s != {RODZAJ_PBN_ARTYKUL})"


def get_lista_prac(nazwa_dyscypliny):
    """Zwraca liste prac - potencjalnych kandydatow do ewaluacji, ale wyłcznie dla dozwolonych
    autorow, tzn posiadajacych udzialy jednostkowe w danej dyscyplinie oraz dla lat 2022-2025
    """
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok

    dozwoleni_autorzy = IloscUdzialowDlaAutoraZaRok.objects.filter(
        dyscyplina_naukowa__nazwa=nazwa_dyscypliny
    ).values_list("autor_id")

    if not dozwoleni_autorzy.exists():
        raise ValueError(
            f"Nie mam żadnych autorów z wgranymi udziałami dla dyscypliny {nazwa_dyscypliny}"
        )

    from bpp.models import Cache_Punktacja_Autora_Query

    return (
        Cache_Punktacja_Autora_Query.objects.filter(
            rekord__rok__gte=const.ROK_MIN,
            rekord__rok__lte=const.ROK_MAX,
            dyscyplina__nazwa=nazwa_dyscypliny,
            autor__in=dozwoleni_autorzy,
        )
        .exclude(rekord__charakter_formalny__charakter_ogolny=None)
        .annotate(
            # stąd się bierze .monografia, monografia=
            monografia=NieArtykul(F("rekord__charakter_formalny__rodzaj_pbn")),
            rok=F("rekord__rok"),
            poziom_wydawcy=F("rekord__wydawca__poziom_wydawcy__poziom"),
        )
        .select_related(
            "rekord",
            "rekord__charakter_formalny",
        )
    )
