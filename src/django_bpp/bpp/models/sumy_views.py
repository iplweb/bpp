# -*- encoding: utf-8 -*-


from django.db.models import DO_NOTHING
from django.db.models.signals import post_delete, pre_delete, post_save
from django.db import models, connection
from django.conf import settings

from bpp.models import Autor, MODELE_PUNKTOWANE, POLA_PUNKTACJI, ModelPunktowany, MODELE_AUTORSKIE
from bpp.util import has_changed


# Poniżej ważne jest to on_delete=DO_NOTHING, ponieważ bez tego Django
# będzie próbowało usuwać dane z tych tabel również, a te tabele to
# są VIEWs od strony SQLa, więc to się na ten moment nie uda (nie licząc
# tych VIEWs w PostgreSQL, które są modyfikowalne...)

class Sumy_Base(ModelPunktowany, models.Model):
    autor = models.ForeignKey('Autor', primary_key=True, on_delete=DO_NOTHING)
    jednostka = models.ForeignKey('Jednostka', on_delete=DO_NOTHING)
    wydzial = models.ForeignKey('Wydzial', on_delete=DO_NOTHING)
    rok = models.IntegerField()

    class Meta:
        app_label = 'bpp'
        managed = False
        abstract = True


class Sumy_View(Sumy_Base):
    class Meta:
        app_label = 'bpp'
        managed = False

Sumy = Sumy_View

class Sumy_Praca_Doktorska_View(Sumy_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Sumy_Praca_Habilitacyjna_View(Sumy_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Sumy_Patent_View(Sumy_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Sumy_Wydawnictwo_Ciagle_View(Sumy_Base):
    class Meta:
        app_label = 'bpp'
        managed = False


class Sumy_Wydawnictwo_Zwarte_View(Sumy_Base):
    class Meta:
        app_label = 'bpp'
        managed = False
