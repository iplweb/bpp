"""
Modele abstrakcyjne związane z opłatami za publikację.
"""

from django.core.exceptions import ValidationError
from django.db import models


class ManagerModeliZOplataZaPublikacjeMixin:
    def rekordy_z_oplata(self):
        return self.exclude(opl_pub_cost_free=None)


class ModelZOplataZaPublikacje(models.Model):
    opl_pub_cost_free = models.BooleanField(
        verbose_name="Publikacja bezkosztowa", null=True
    )
    opl_pub_research_potential = models.BooleanField(
        verbose_name="Środki finansowe art. 365 pkt 2 ustawy",
        null=True,
        help_text="Środki finansowe, o których mowa w art. 365 pkt 2 ustawy",
    )
    opl_pub_research_or_development_projects = models.BooleanField(
        verbose_name="Środki finansowe na realizację projektu",
        null=True,
        help_text="Środki finansowe przyznane na realizację projektu "
        "w zakresie badań naukowych lub prac rozwojowych",
    )

    opl_pub_other = models.BooleanField(
        verbose_name="Inne środki finansowe", null=True, blank=True, default=None
    )

    opl_pub_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Kwota brutto (zł)",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    def _waliduj_publikacje_bezkosztowa(self):
        """Validate cost-free publication."""
        if self.opl_pub_amount is not None and self.opl_pub_amount > 0:
            # ... musi mieć kwotę za publikację równą zero
            raise ValidationError(
                {
                    "opl_pub_amount": "Publikacja bezkosztowa, ale kwota opłaty za publikację większa od zera."
                    "Proszę o skorygowanie"
                }
            )

        if (
            self.opl_pub_research_potential
            or self.opl_pub_research_or_development_projects
            or self.opl_pub_other
        ):
            # ... oraz odznaczone pozostałe pola
            errmsg = """Jeżeli zaznaczono publikację jako bezkosztową, to pozostałe pola dotyczące
            środków finansowych nie mogą być zaznaczone na 'TAK', a koszt powinien być równy 0.00 zł. Przejrzyj
            te pola i odznacz je. """

            errmsg2 = """Pole nie może być zaznaczone na 'TAK' dla publikacji bezkosztowej. """

            errdct = {
                "opl_pub_cost_free": errmsg,
            }

            if self.opl_pub_research_potential:
                errdct["opl_pub_research_potential"] = errmsg2

            if self.opl_pub_research_or_development_projects:
                errdct["opl_pub_research_or_development_projects"] = errmsg2

            if self.opl_pub_other:
                errdct["opl_pub_other"] = errmsg2

            raise ValidationError(errdct)

    def _waliduj_publikacje_kosztowa(self):
        """Validate paid publication."""
        if self.opl_pub_amount is not None and self.opl_pub_amount > 0:
            # ...jeżeli ma wpisany koszt, musi miec zaznaczony któreś z pól:
            if (
                not self.opl_pub_research_or_development_projects
                and not self.opl_pub_research_potential
                and not self.opl_pub_other
            ):
                errmsg = (
                    "Jeżeli wpisano opłatę za publikację, należy dodatkowo zaznaczyć, z jakich środków"
                    " została ta opłata zrealizowana. Przejrzyj pola dotyczące środków finansowych "
                    "i ustaw wartość na 'TAK' przynajmniej w jednym z nich - np w tym ... "
                )

                errmsg2 = "... lub w tym ..."
                errmsg3 = "... lub tutaj. "

                raise ValidationError(
                    {
                        "opl_pub_research_potential": errmsg,
                        "opl_pub_research_or_development_projects": errmsg2,
                        "opl_pub_other": errmsg3,
                    }
                )

        else:
            # ... jeżeli nie ma wpisanego kosztu a ma zaznaczone któreś z pól to też źle
            if (
                self.opl_pub_research_or_development_projects
                or self.opl_pub_research_potential
                or self.opl_pub_other
            ):
                errdct = {"opl_pub_amount": "Tu należy uzupełnić kwotę. "}

                errmsg = (
                    "Jeżeli wybrano pola dotyczące opłaty za publikację, należy dodatkowo wpisać kwotę... "
                    "lub od-znaczyć te pola. "
                )

                if self.opl_pub_research_potential:
                    errdct["opl_pub_research_potential"] = errmsg

                if self.opl_pub_research_or_development_projects:
                    errdct["opl_pub_research_or_development_projects"] = errmsg

                if self.opl_pub_other:
                    errdct["opl_pub_other"] = errmsg

                raise ValidationError(errdct)
            else:
                if self.opl_pub_cost_free is not None:
                    # jeżeli nie ma wpisanego kosztu i nie ma zaznaczonego
                    # zadnego z pól to tym bardziej źle
                    errdct = {"opl_pub_amount": "Tu należy uzupełnić kwotę. "}

                    errmsg = (
                        "Jeżeli publikacja nie była bezkosztowa, należy zaznaczyć "
                        "przynajmniej jedno z tych pól"
                    )

                    errdct["opl_pub_research_potential"] = errmsg
                    errdct["opl_pub_research_or_development_projects"] = errmsg
                    errdct["opl_pub_other"] = errmsg

                    raise ValidationError(errdct)

    def clean(self):
        if self.opl_pub_cost_free:
            self._waliduj_publikacje_bezkosztowa()
        else:
            self._waliduj_publikacje_kosztowa()
