from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import PositiveSmallIntegerField, CASCADE, CASCADE
from mptt.models import MPTTModel, TreeForeignKey


class Dyscyplina_Naukowa(MPTTModel):
    nazwa = models.CharField(max_length=200, unique=True)
    kod = models.CharField(max_length=20, null=True, blank=True, unique=True)
    widoczna = models.BooleanField(default=True)

    dyscyplina_nadrzedna = TreeForeignKey(
        'self', CASCADE,
        null=True,
        blank=True,
        related_name='subdyscypliny',
        db_index=True)

    class MPTTMeta:
        order_insertion_by = ['nazwa']
        parent_attr = 'dyscyplina_nadrzedna'

    def __str__(self):
        return f"{ self.nazwa } ({ self.kod })"

    class Meta:
        verbose_name_plural = "dyscypliny naukowe"
        verbose_name = "dyscyplina naukowa"


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

                i = elem.dyscyplina_nadrzedna
                while i is not None:
                    if not i.widoczna:
                        i.widoczna = True
                        i.save()
                    i = i.dyscyplina_nadrzedna


class Autor_Dyscyplina(models.Model):
    rok = PositiveSmallIntegerField()
    autor = models.ForeignKey("bpp.Autor", CASCADE)

    dyscyplina_naukowa = models.ForeignKey("bpp.Dyscyplina_Naukowa", models.PROTECT, related_name="dyscyplina")
    procent_dyscypliny = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    subdyscyplina_naukowa = models.ForeignKey("bpp.Dyscyplina_Naukowa", models.PROTECT, related_name="subdyscyplina", blank=True, null=True)
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
