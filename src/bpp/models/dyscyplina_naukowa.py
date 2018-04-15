from django.db import models, transaction
from django.db.models import PositiveSmallIntegerField
from mptt.models import MPTTModel, TreeForeignKey


class Dyscyplina_Naukowa(MPTTModel):
    nazwa = models.CharField(max_length=200, unique=True)
    kod = models.CharField(max_length=20, null=True, blank=True, unique=True)
    widoczna = models.BooleanField(default=True)

    dyscyplina_nadrzedna = TreeForeignKey(
        'self',
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

        for elem in self.all().values("dyscyplina").distinct():
            elem = Dyscyplina_Naukowa.objects.get(pk=elem['dyscyplina'])
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
    autor = models.ForeignKey("bpp.Autor")
    dyscyplina = models.ForeignKey("bpp.Dyscyplina_Naukowa")

    objects = Autor_DyscyplinaManager()

    class Meta:
        unique_together = [
            ('rok', 'autor')
        ]
        verbose_name = "powiązanie autora z dyscypliną naukową"
        verbose_name_plural = "powiązania autorów z dyscyplinami naukowymi"
