from django.db import models
from django.db.models import CASCADE

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

from django.utils.functional import cached_property

from bpp.models import Autor, Charakter_Formalny, DwaTytuly, ModelZOplataZaPublikacje
from bpp.models.praca_doktorska import Praca_Doktorska_Baza


class Publikacja_Habilitacyjna(models.Model):
    praca_habilitacyjna = models.ForeignKey("Praca_Habilitacyjna", CASCADE)
    kolejnosc = models.IntegerField("Kolejność", default=0)

    limit = (
        models.Q(app_label="bpp", model="wydawnictwo_ciagle")
        | models.Q(app_label="bpp", model="wydawnictwo_zwarte")
        | models.Q(app_label="bpp", model="patent")
    )
    content_type = models.ForeignKey(ContentType, CASCADE, limit_choices_to=limit)
    object_id = models.PositiveIntegerField()
    publikacja = GenericForeignKey()

    class Meta:
        app_label = "bpp"
        verbose_name = "powiązanie publikacji z habilitacją"
        verbose_name_plural = "powiązania publikacji z habilitacją"
        unique_together = [("praca_habilitacyjna", "content_type", "object_id")]
        ordering = ("kolejnosc",)


class _Praca_Habilitacyjna_PropertyCache:
    @cached_property
    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="H")


_Praca_Habilitacyjna_PropertyCache = _Praca_Habilitacyjna_PropertyCache()


class Praca_Habilitacyjna(Praca_Doktorska_Baza):
    autor = models.OneToOneField(Autor, CASCADE)

    publikacje_habilitacyjne = GenericRelation(Publikacja_Habilitacyjna)

    @cached_property
    def charakter_formalny(self):
        return _Praca_Habilitacyjna_PropertyCache.charakter_formalny

    class Meta:
        verbose_name = "praca habilitacyjna"
        verbose_name_plural = "prace habilitacyjne"
        app_label = "bpp"

    def clean(self):
        DwaTytuly.clean(self)
        ModelZOplataZaPublikacje.clean(self)
