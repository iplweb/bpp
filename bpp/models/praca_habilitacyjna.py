# -*- encoding: utf-8 -*-
from django.contrib.contenttypes.fields import GenericForeignKey, \
    GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from bpp.models.praca_doktorska import Praca_Doktorska_Baza
from django.contrib.contenttypes import generic


class Publikacja_Habilitacyjna(models.Model):
    praca_habilitacyjna = models.ForeignKey('Praca_Habilitacyjna')
    kolejnosc = models.IntegerField('Kolejność', default=0)
    
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    publikacja = GenericForeignKey()

    class Meta:
        app_label = 'bpp'
        verbose_name = "powiązanie publikacji z habilitacją"
        verbose_name_plural = "powiązania publikacji z habilitacją"
        ordering = ('kolejnosc',)


class Praca_Habilitacyjna(Praca_Doktorska_Baza):
    publikacje_habilitacyjne = GenericRelation(Publikacja_Habilitacyjna)

    class Meta:
        verbose_name = 'praca habilitacyjna'
        verbose_name_plural = 'prace habilitacyjne'
        app_label = 'bpp'


