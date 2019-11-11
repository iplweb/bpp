from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import PositiveSmallIntegerField, CASCADE

from bpp.models import const

# bpp=# select distinct substr(id, 1, 2), dziedzina from import_dbf_ldy;
#  substr |                 dziedzina
# --------+--------------------------------------------
#  01     | Dziedzina nauk humanistycznych
#  02     | Dziedzina nauk inżynieryjno-technicznych
#  03     | Dziedzina nauk medycznych i nauk o zdrowiu
#  04     | Dziedzina nauk rolniczych
#  05     | Dziedzina nauk społecznych
#  06     | Dziedzina nauk ścisłych i przyrodniczych
#  07     | Dziedzina nauk teologicznych
#  08     | Dziedzina sztuki
# (8 rows)


class Dyscyplina_Naukowa(models.Model):
    kod = models.CharField(max_length=20, unique=True)
    nazwa = models.CharField(max_length=200, unique=True)
    widoczna = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nazwa} ({self.kod})"

    class Meta:
        verbose_name_plural = "dyscypliny naukowe"
        verbose_name = "dyscyplina naukowa"

    def dziedzina(self):
        try:
            nadkod = int(self.kod.lstrip("0").strip().split(".")[0])
            return const.DZIEDZINY.get(nadkod)
        except (ValueError, TypeError, KeyError):
            pass


class Autor_DyscyplinaManager(models.Manager):
    @transaction.atomic
    def ukryj_nieuzywane(self):
        # Ukryj dyscypliny nieużywane
        for elem in Dyscyplina_Naukowa.objects.all():
            elem.widoczna = False
            elem.save()

        for attr in "dyscyplina_naukowa", "subdyscyplina_naukowa":
            for elem in self.all().values(attr).distinct():
                if elem[attr] is None:
                    continue

                elem = Dyscyplina_Naukowa.objects.get(pk=elem[attr])
                elem.widoczna = True
                elem.save()


class Autor_Dyscyplina(models.Model):
    rok = PositiveSmallIntegerField()
    autor = models.ForeignKey("bpp.Autor", CASCADE)

    dyscyplina_naukowa = models.ForeignKey("bpp.Dyscyplina_Naukowa", models.PROTECT, related_name="dyscyplina")
    procent_dyscypliny = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    subdyscyplina_naukowa = models.ForeignKey("bpp.Dyscyplina_Naukowa", models.PROTECT, related_name="subdyscyplina",
                                              blank=True, null=True)
    procent_subdyscypliny = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    objects = Autor_DyscyplinaManager()

    class Meta:
        unique_together = [
            ('rok', 'autor')
        ]
        verbose_name = "powiązanie autora z dyscypliną naukową"
        verbose_name_plural = "powiązania autorów z dyscyplinami naukowymi"

    def clean(self):
        p1 = self.procent_dyscypliny or Decimal("0.00")
        p2 = self.procent_subdyscypliny or Decimal("0.00")

        if p1 + p2 > Decimal("100.00"):
            raise ValidationError({"procent_dyscypliny": "Suma procentów przekracza 100."})

        if hasattr(self, 'dyscyplina_naukowa') and hasattr(self, 'subdyscyplina_naukowa'):
            if self.dyscyplina_naukowa_id == self.subdyscyplina_naukowa_id:
                raise ValidationError({"subdyscyplina_naukowa": "Wpisano tą samą dyscyplinę dwukrotnie."})
