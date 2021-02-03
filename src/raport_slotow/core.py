from typing import List, Tuple

from bpp.models import Autor_Dyscyplina, Cache_Punktacja_Autora_Query_View


def _get_kwargs(od_roku, do_roku, prefix=""):
    kwargs = dict()
    if od_roku:
        kwargs[f"{prefix}rok__gte"] = od_roku

    if do_roku:
        kwargs[f"{prefix}rok__lte"] = do_roku
    return kwargs


def autorzy_z_dyscyplinami(od_roku=None, do_roku=None) -> List[Tuple[int, int, int]]:
    """
    Zwraca listę autorów z dyscyplinami z bazy danych

    :returns: listę z krotkami z których każda krotka ma następujące wartości:
        ID autora, rok, ID dyscypliny naukowej
    """

    kwargs = _get_kwargs(od_roku, do_roku)

    return (
        Autor_Dyscyplina.objects.values("autor_id", "rok", "dyscyplina_naukowa_id")
        .filter(**kwargs)
        .exclude(dyscyplina_naukowa_id=None)
        .union(
            Autor_Dyscyplina.objects.values(
                "autor_id", "rok", "subdyscyplina_naukowa_id"
            )
            .exclude(subdyscyplina_naukowa_id=None)
            .filter(**kwargs)
        )
    )


def autorzy_z_punktami(
    od_roku=None, do_roku=None, min_pk=None
) -> List[Tuple[int, int, int]]:
    """
    Zwraca listę autorów z dyscyplinami z punktami z bazy danych

    """

    kwargs = _get_kwargs(od_roku, do_roku, prefix="rekord__")

    exclude_kwargs = dict()
    if min_pk is not None:
        exclude_kwargs = dict(rekord__punkty_kbn__lte=min_pk)

    return (
        Cache_Punktacja_Autora_Query_View.objects.all()
        .filter(**kwargs)
        .exclude(**exclude_kwargs)
        .values("autor_id", "rekord__rok", "dyscyplina_id")
    )


def autorzy_zerowi(od_roku=None, do_roku=None, min_pk=None):
    """
    Zwraca listę krotek w postaci (autor_id, rok, dyscyplina_id) która zawiera listę
    autorów zerowych czyli autorów, którzy mimo zadeklarowanych na dany rok dyscyplin
    nie posiadają w bazie żadnych punktowanych rekordów.
    """
    # wartośći zadeklarowane w bazie danych
    defined = autorzy_z_dyscyplinami(od_roku=od_roku, do_roku=do_roku)

    # zestawy autor/rok/dyscyplina z całej bazy danych
    existent = autorzy_z_punktami(od_roku=od_roku, do_roku=do_roku, min_pk=min_pk)

    return defined.difference(existent)
