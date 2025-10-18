from collections import namedtuple
from datetime import datetime

from django.contrib.postgres.aggregates import ArrayAgg

from bpp.models import Cache_Punktacja_Autora_Query
from bpp.util import intsack
from ewaluacja_common.utils import get_lista_prac


def get_lista_autorow_na_rekord(nazwa_dyscypliny):
    return {
        x["rekord_id"]: tuple(x["autorzy"])
        for x in get_lista_prac(nazwa_dyscypliny)
        .values("rekord_id")
        .annotate(autorzy=ArrayAgg("autor_id"))
        .order_by()
    }


def lista_prac_na_tuples(lista_prac: list[Cache_Punktacja_Autora_Query], lista_autorow):
    return tuple(
        Praca(
            id=elem.id,
            rekord_id=elem.rekord_id,
            slot=elem.slot,
            autor_id=elem.autor_id,
            rok=elem.rekord.rok,
            pkdaut=elem.pkdaut,
            monografia=elem.monografia,
            poziom_wydawcy=elem.poziom_wydawcy,
            autorzy=lista_autorow.get(elem.rekord_id),
            ostatnio_zmieniony=elem.rekord.ostatnio_zmieniony,
        )
        for elem in lista_prac
    )


def get_lista_prac_as_tuples(nazwa_dyscypliny):
    return lista_prac_na_tuples(
        list(get_lista_prac(nazwa_dyscypliny)),
        get_lista_autorow_na_rekord(nazwa_dyscypliny),
    )


def policz_knapsack(lista_prac, maks_slot=4.0):
    res = intsack(
        maks_slot,
        [x.slot for x in lista_prac],
        [x.pkdaut for x in lista_prac],
        [x for x in lista_prac],
    )
    return res


def encode_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(
        "Object of type %s is not JSON serializable" % obj.__class__.__name__
    )


def maks_pkt_aut_calosc_get_from_db(nazwa_dyscypliny):
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok

    return {
        int(x["autor_id"]): x["ilosc_udzialow"]
        for x in IloscUdzialowDlaAutoraZaRok.objects.filter(
            dyscyplina_naukowa__nazwa=nazwa_dyscypliny
        ).values("autor_id", "ilosc_udzialow")
    }


def maks_pkt_aut_monografie_get_from_db(nazwa_dyscypliny):
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok

    return {
        int(x["autor_id"]): x["ilosc_udzialow_monografie"]
        for x in IloscUdzialowDlaAutoraZaRok.objects.filter(
            dyscyplina_naukowa__nazwa=nazwa_dyscypliny
        ).values("autor_id", "ilosc_udzialow_monografie")
    }


def splitEveryN(n, it):
    return [it[i : i + n] for i in range(0, len(it), n)]


Praca = namedtuple(
    "Praca",
    [
        "id",
        "rekord_id",
        "slot",
        "autor_id",
        "rok",
        "pkdaut",
        "monografia",
        "poziom_wydawcy",
        "autorzy",
        "ostatnio_zmieniony",
    ],
)
