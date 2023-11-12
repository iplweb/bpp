from django.db import models

from ..exceptions import TlumaczDyscyplinException


class TlumaczDyscyplinManager(models.Manager):
    def przetlumacz_dyscypline(
        self, dyscyplina_bpp: "bpp.models.Dyscyplina_Naukowa", rok: int  # noqa: F821
    ):
        try:
            td: TlumaczDyscyplin = self.get(dyscyplina_w_bpp=dyscyplina_bpp)
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

        if rok >= 2017 and rok <= 2021:
            if td.pbn_2017_2021 is not None:
                return td.pbn_2017_2021

            raise BrakWpisuException
        elif rok >= 2022:
            if td.pbn_2022_now is not None:
                return td.pbn_2022_now

            raise BrakWpisuException

        raise BrakWpisuException


class TlumaczDyscyplin(models.Model):
    """Obiekt tłumaczący dyscyplinę w BPP na dyscyplinę w PBNie.

    Ponieważ w PBNie obowiązują różne słowniki, ale nie w datach które te słowniki
    posiadają ustawione w swoim atrybucie ale w konkretnych zakresach, stąd też
    nazwy pól dla pbn_uid w tym obiekcie.

    """

    objects = TlumaczDyscyplinManager()

    dyscyplina_w_bpp = models.OneToOneField(
        "bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE
    )
    pbn_2017_2021 = models.ForeignKey(
        "pbn_api.Discipline",
        verbose_name="Dyscyplina w PBN 2017-2021",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dyscyplina_bpp_2017_2021",
    )
    pbn_2022_now = models.ForeignKey(
        "pbn_api.Discipline",
        verbose_name="Dyscyplina w PBN 2022-teraz",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dyscyplina_bpp_2022_now",
    )

    def __str__(self):
        ret = f"Tłumaczy dyscyplinę {self.dyscyplina_w_bpp} na"

        app = []
        if self.pbn_2022_now_id is not None:
            app.append(f"aktualną w PBN {self.pbn_2022_now}")
        if self.pbn_2017_2021_id is not None:
            app.append(f"nieaktualną w PBN za 2017-2021 {self.pbn_2017_2021}")

        if app:
            return ret + " " + ", ".join(app)
        return ret + " nic -- brak wpisów odpowiedników PBN w rekordzie."

    class Meta:
        verbose_name = "rekord tłumacza dyscyplin BPP do PBN"
        verbose_name_plural = "rekordy tłumacza dyscyplin BPP do PBN"
        ordering = ("dyscyplina_w_bpp__nazwa",)
