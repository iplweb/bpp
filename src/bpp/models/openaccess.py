# -*- encoding: utf-8 -*-
from bpp.models.abstract import NazwaISkrot


class Tryb_OpenAccess_Wydawnictwo_Ciagle(NazwaISkrot):
    class Meta:
        verbose_name = u"tryb OpenAccess wyd. ciągłych"
        verbose_name_plural = u"tryby OpenAccess wyd. ciągłych"
        ordering = ['nazwa']
        app_label = 'bpp'


class Tryb_OpenAccess_Wydawnictwo_Zwarte(NazwaISkrot):
    class Meta:
        verbose_name = u"tryb OpenAccess wyd. zwartych"
        verbose_name_plural = u"tryby OpenAccess wyd. zwartych"
        ordering = ['nazwa']
        app_label = 'bpp'


class Czas_Udostepnienia_OpenAccess(NazwaISkrot):
    class Meta:
        verbose_name = u'czas udostępnienia OpenAccess'
        verbose_name_plural = u'czasy udostępnienia OpenAccess'
        ordering = ['nazwa']
        app_label = 'bpp'


class Licencja_OpenAccess(NazwaISkrot):
    class Meta:
        verbose_name = u'licencja OpenAccess'
        verbose_name_plural = u'licencja OpenAccess'
        ordering = ['nazwa']
        app_label = 'bpp'


class Wersja_Tekstu_OpenAccess(NazwaISkrot):
    class Meta:
        verbose_name = u'wersja tekstu OpenAccess'
        verbose_name_plural = u'wersje tekstu OpenAccess'
        ordering = ['nazwa']
        app_label = 'bpp'
