# -*- encoding: utf-8 -*-

from django.db import models
from django.db.models import DO_NOTHING
from bpp.util import get_original_object


class Kronika_View_Base(models.Model):
    autor = models.ForeignKey('bpp.Autor', on_delete=DO_NOTHING)
    imiona = models.TextField()
    nazwisko = models.TextField()
    jednostka = models.ForeignKey('bpp.Jednostka', on_delete=DO_NOTHING)
    tytul_oryginalny = models.TextField()
    rok = models.IntegerField()
    kolejnosc = models.IntegerField()
    object = models.TextField()
    object_pk = models.IntegerField()
    zrodlo = models.ForeignKey('bpp.Zrodlo', on_delete=DO_NOTHING)
    id = models.IntegerField(primary_key=True)

    def get_original_object(self):
        return get_original_object(self.object, self.object_pk)

    class Meta:
        app_label = 'bpp'
        managed = False
        abstract = True
        unique_together = [('object', 'object_pk')]


class Kronika_Wydawnictwo_Ciagle_View(Kronika_View_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Kronika_Wydawnictwo_Zwarte_View(Kronika_View_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Kronika_Patent_View(Kronika_View_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Kronika_Praca_Doktorska_View(Kronika_View_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Kronika_Praca_Habilitacyjna_View(Kronika_View_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Kronika_View(Kronika_View_Base):
    class Meta:
        app_label = 'bpp'
        managed = False

#
# class Kronika_Numerki_View(models.Model):
#     rok = models.IntegerField()
#     object = models.TextField()
#     object_pk = models.IntegerField()
#     id = models.IntegerField(primary_key=True) # Numerek!
#
#     class Meta:
#         app_label = 'bpp'
#         managed = False
#
#     def get_original_object(self):
#         return get_original_object(self.object, self.object_pk)
#
