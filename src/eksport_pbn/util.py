# -*- encoding: utf-8 -*-
from datetime import timedelta

from bpp.models.system import Charakter_Formalny, Typ_KBN
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor, Wydawnictwo_Zwarte
from eksport_pbn.models import DATE_CREATED_ON, DATE_UPDATED_ON, DATE_UPDATED_ON_PBN


class ExportPBNException(Exception):
    pass


class BrakTakiegoRodzajuDatyException(ExportPBNException):
    pass


def data_kw(rodzaj_daty, od_daty, do_daty=None):
    if od_daty is None or rodzaj_daty is None:
        return {}

    flds = {DATE_CREATED_ON: 'utworzono',
            DATE_UPDATED_ON: 'ostatnio_zmieniony',
            DATE_UPDATED_ON_PBN: 'ostatnio_zmieniony_dla_pbn'}

    ret = {}

    try:
        ret['rekord__%s__gte' % flds[rodzaj_daty]] = od_daty
    except KeyError:
        raise BrakTakiegoRodzajuDatyException(rodzaj_daty)

    if do_daty:
        ret['rekord__%s__lte' % flds[rodzaj_daty]] = \
            do_daty + timedelta(days=1)

    return ret


def id_ciaglych(wydzial, od_roku, do_roku, rodzaj_daty=None, od_daty=None, do_daty=None):
    return Wydawnictwo_Ciagle_Autor.objects.filter(
        jednostka__wydzial=wydzial,
        rekord__rok__gte=od_roku,
        rekord__rok__lte=do_roku,
        rekord__charakter_formalny__in=Charakter_Formalny.objects.filter(artykul_pbn=True),
        rekord__typ_kbn__in=Typ_KBN.objects.filter(artykul_pbn=True),
        **data_kw(rodzaj_daty, od_daty, do_daty)
    ).order_by("rekord_id").distinct("rekord_id").only("rekord_id").values_list("rekord_id", flat=True)


def id_zwartych(wydzial, od_roku, do_roku, ksiazki, rozdzialy, rodzaj_daty=None, od_daty=None, do_daty=None):
    ksiazki_query = Wydawnictwo_Zwarte_Autor.objects.filter(
        jednostka__wydzial=wydzial,
        rekord__rok__gte=od_roku,
        rekord__rok__lte=do_roku,
        rekord__charakter_formalny__in=Charakter_Formalny.objects.filter(ksiazka_pbn=True),
        rekord__liczba_znakow_wydawniczych__gte=240000,
        **data_kw(rodzaj_daty, od_daty, do_daty)
    ).order_by("rekord_id").distinct("rekord_id").only("rekord_id")

    if ksiazki:
        for rekord in ksiazki_query.values_list("rekord_id", flat=True):
            yield rekord

    if rozdzialy:

        rozdzialy_query = Wydawnictwo_Zwarte_Autor.objects.filter(
            jednostka__wydzial=wydzial,
            rekord__rok__gte=od_roku,
            rekord__rok__lte=do_roku,
            rekord__charakter_formalny__in=Charakter_Formalny.objects.filter(rozdzial_pbn=True),
            rekord__liczba_znakow_wydawniczych__gt=0,
            **data_kw(rodzaj_daty, od_daty, do_daty)
        ).order_by("rekord_id").distinct("rekord_id").only("rekord_id")

        for rekord in rozdzialy_query.values_list("rekord_id", flat=True):
            yield rekord
