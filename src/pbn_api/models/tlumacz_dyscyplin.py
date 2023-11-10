from django.db import models

from ..exceptions import TlumaczDyscyplinException
from .discipline import Discipline


class TlumaczDyscyplinManager(models.Model):
    import bpp

    def tlumacz_dyscypline(
        self, dyscyplina_bpp: "bpp.models.Dyscyplina_Naukowa", rok: int
    ):
        try:
            td: TlumaczDyscyplin = self.get(dyscyplina_bpp=dyscyplina_bpp)
        except TlumaczDyscyplin.DoesNotExist:
            raise TlumaczDyscyplinException(
                f"Nie mogę przetłumaczyć dyscypliny {dyscyplina_bpp} do dyscypliny w PBN, "
                f"bo w Tłumaczu Dyscyplin PBN API w ogóle brakuje wpisu dla tej dyscypliny!"
            )

        BrakWpisuException = TlumaczDyscyplinException(
            f"Nie mogę przetłumaczyć dyscypliny {dyscyplina_bpp} dla roku {rok}, "
            f"ponieważ w Tłumaczu Dyscyplin PBN API nie ma wpisu dla tego roku dla "
            f"tej dyscypliny. "
        )

        if rok >= 2018 and rok <= 2021:
            try:
                return td.pbn_2017_2021
            except Discipline.DoesNotExist:
                raise BrakWpisuException
        elif rok >= 2022:
            try:
                return td.pbn_2022_now
            except Discipline.DoesNotExist:
                raise BrakWpisuException

        raise BrakWpisuException


class TlumaczDyscyplin(models.Model):
    """Obiekt tłumaczący dyscyplinę w BPP na dyscyplinę w PBNie.

    Ponieważ w PBNie obowiązują różne słowniki, ale nie w datach które te słowniki
    posiadają ustawione w swoim atrybucie ale w konkretnych zakresach, stąd też
    nazwy pól dla pbn_uid w tym obiekcie.

    """

    dyscyplina_w_bpp = models.OneToOneField(
        "bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE
    )
    pbn_2017_2021 = models.ForeignKey(
        "pbn_api.Discipline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dyscyplina_bpp_2017_2021",
    )
    pbn_2022_now = models.ForeignKey(
        "pbn_api.Discipline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dyscyplina_bpp_2022_now",
    )
