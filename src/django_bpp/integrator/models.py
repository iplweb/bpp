# -*- encoding: utf-8 -*-
import logging

from django.db import models
from django.contrib.auth import get_user_model
from bpp.models import Autor, Jednostka
from django.conf import settings
import os
from bpp.util import slugify_function

STATUSY = [
    (0, "dodany"),
    (1, "w trakcie analizy"),
    (2, "przetworzony"),
    (3, "przetworzony z błędami")
]


class AutorIntegrationFile(models.Model):
    name = models.CharField("Nazwa", max_length=255)
    file = models.FileField(verbose_name="Plik", upload_to="integrator")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL)
    uploaded_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True, auto_now_add=True)
    status = models.IntegerField(choices=STATUSY, default=STATUSY[0][0])
    extra_info = models.TextField()

    def filename(self):
        return os.path.basename(self.file.name)

    def records(self):
        return self.autorintegrationrecord_set.all()

    def integrated(self):
        return self.records().filter(zintegrowano=True)

    def not_integrated(self):
        return self.records().exclude(zintegrowano=True).order_by('extra_info')

    class Meta:
        verbose_name = "Plik integracji autorów"
        ordering = ['-last_updated_on']

AUTOR_IMPORT_COLUMNS = {
    u"Tytuł/Stopień": "tytul_skrot",
    u"Nazwisko": "nazwisko",
    u"Imię": "imie",
    u"Nazwa jednostki": "nazwa_jednostki",
    u"PBN ID": "pbn_id"
}


def int_or_None(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


class AutorIntegrationRecord(models.Model):
    parent = models.ForeignKey(AutorIntegrationFile)

    tytul_skrot = models.TextField()
    nazwisko = models.TextField()
    imie = models.TextField()
    nazwa_jednostki = models.TextField()
    pbn_id = models.TextField()

    matching_autor = models.ForeignKey(Autor, null=True)
    matching_jednostka = models.ForeignKey(Jednostka, null=True)
    zanalizowano = models.BooleanField(default=False)
    moze_byc_zintegrowany_automatycznie = models.BooleanField(default=False)
    zintegrowano = models.BooleanField(default=False)
    extra_info = models.TextField()

    def sprobuj_zlokalizowac_autora(self):
        strategia_1 = lambda self: Autor.objects.filter(nazwisko=self.nazwisko, imiona=self.imie)
        strategia_2 = lambda self: Autor.objects.filter(nazwisko__icontains=self.nazwisko, imiona__icontains=self.imie)
        strategia_3 = lambda self: Autor.objects.filter(
            pk=int_or_None("".join(self.nazwisko.split(",")[1:2]).strip()))
        strategia_4 = lambda self: Autor.objects.filter(
            poprzednie_nazwiska__icontains=self.nazwisko, imiona__icontains=self.imie)

        for strategia in [strategia_1, strategia_2, strategia_3, strategia_4]:
            ret = strategia(self)

            if ret.count() == 0:
                continue

            if ret.count() == 1:
                self.matching_autor = list(ret)[0]
                self.save()
                return True

            # Jest wiecej, niz jeden pasujacy autor, sprawdz wobec tego po jednostce
            for autor in ret:
                # Poszukaj ciągu self.nazwa_jednostki w jednostkach danego autora
                ret_jed = autor.jednostki.filter(nazwa=self.nazwa_jednostki)
                if ret_jed.count() == 1:
                    self.matching_autor = autor
                    self.matching_jednostka = list(ret_jed)[0]
                    self.save()
                    return True

    def sprobuj_zlokalizowac_jednostke(self):
        # Zakładamy, że wcześniej uruchomiono self.sprobuj_zlokalizowac_autora oraz, ze
        # self.matchin_autor jest nie-pusty.

        # UWAGA: autor moze byc nie-przypisany do tej jednostki

        strategia_1 = Jednostka.objects.filter(nazwa__icontains=self.nazwa_jednostki.strip())[:3]
        strategia_2 = Jednostka.objects.filter(nazwa=self.nazwa_jednostki.strip())[:3]
        strategia_3 = Jednostka.objects.filter(nazwa=self.nazwa_jednostki)[:3]
        strategia_4 = Jednostka.objects.filter(slug=slugify_function(self.nazwa_jednostki)[:50])[:3]
        strategia_5 = Jednostka.objects.filter(nazwa=unicode("%r" % self.nazwa_jednostki))[:3]
        strategia_6 = Jednostka.objects.filter(slug=slugify_function(unicode("%r" % self.nazwa_jednostki))[:50])[:3]

        log = [u"Ciąg: |%s|" % self.nazwa_jednostki]

        for no, strategia in enumerate([strategia_1, strategia_2, strategia_3, strategia_4, strategia_5, strategia_6]):
            res = list(strategia)
            log.append(u"%s: %s" % (no, len(strategia)))

            if len(strategia) == 1:
                self.matching_jednostka = strategia[0]
                self.save()
                return True

        return u", ".join(log)