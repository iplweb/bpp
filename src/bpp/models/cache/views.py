from django.db import models
from django.db.models.deletion import DO_NOTHING
from taggit.models import Tag

from django.contrib.postgres.fields.array import ArrayField


class SlowaKluczoweView(models.Model):
    id = ArrayField(base_field=models.IntegerField(), size=3, primary_key=True)

    rekord = models.ForeignKey(
        "bpp.Rekord", related_name="slowa_kluczowe_set", on_delete=DO_NOTHING
    )
    tag = models.ForeignKey(Tag, on_delete=DO_NOTHING)

    @classmethod
    def tag_relname(cls):
        field = cls._meta.get_field("tag")
        return field.remote_field.related_name

    @classmethod
    def tags_for(cls, model, instance=None, **kwargs):
        from .rekord import Rekord

        if model != Rekord:
            raise NotImplementedError
        if instance is not None:
            return cls.objects.filter(rekord_id=(instance.pk,))
        return cls.objects.all()

    class Meta:
        managed = False
        db_table = "bpp_slowa_kluczowe_view"


class ZewnetrzneBazyDanychView(models.Model):
    rekord = models.ForeignKey(
        "bpp.Rekord", related_name="zewnetrzne_bazy", on_delete=DO_NOTHING
    )

    baza = models.ForeignKey("bpp.Zewnetrzna_Baza_Danych", on_delete=DO_NOTHING)

    info = models.TextField()

    class Meta:
        managed = False
        db_table = "bpp_zewnetrzne_bazy_view"
