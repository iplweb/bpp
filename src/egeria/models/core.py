# -*- encoding: utf-8 -*-

import xlrd
from django.db import models
from django.conf import settings

from egeria.models.funkcja_autora import Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete
from egeria.models.jednostka import Diff_Jednostka_Create, Diff_Jednostka_Delete, Diff_Jednostka_Update
from egeria.models.tytul import Diff_Tytul_Create, Diff_Tytul_Delete
from egeria.models.wydzial import Diff_Wydzial_Create, Diff_Wydzial_Delete


class AlreadyAnalyzedError(Exception):
    pass


class EgeriaImport(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True)
    file = models.FileField(upload_to="egeria_xls")
    analyzed = models.BooleanField(default=False)

    def analyze(self):
        """Wczytuje plik XLS do bazy danych - tworzy potomne rekordy egeria.models.EgeriaRow"""
        if self.analyzed:
            raise AlreadyAnalyzedError
        x = xlrd.open_workbook(self.file.path)
        sheet = x.sheet_by_index(0)

        for nrow in range(5, sheet.nrows):
            # [number:1.0, text:u'dr n. med.', text:u'Kowalska', text:u'Oleg', text:u'12121200587', text:u'Adiunkt', text:u'II Katedra i Klinika Chirurgii Og\xf3lnej, Gastroenterologicznej i Nowotwor\xf3w Uk\u0142adu Pokarmowego', text:u'I Wydzia\u0142 Lekarski z Oddzia\u0142em Stomatologicznym']
            lp, tytul_stopien, nazwisko, imie, pesel_md5, stanowisko, nazwa_jednostki, wydzial = [cell.value for cell in
                                                                                                  sheet.row(nrow)]

            EgeriaRow.objects.create(
                parent=self,
                lp=lp,
                tytul_stopien=tytul_stopien,
                nazwisko=nazwisko,
                imie=imie,
                pesel_md5=pesel_md5,
                stanowisko=stanowisko,
                nazwa_jednostki=nazwa_jednostki,
                wydzial=wydzial
            )

        self.analyzed = True
        self.save()

    def rows(self):
        return EgeriaRow.objects.filter(parent=self)

    def diffs(self, klass):
        return klass.objects.filter(parent=self)

    def commit(self, lst):
        map(lambda x: x.commit(), lst)

    def diff_tytuly(self):
        from egeria.diff_producers.nazwa_i_skrot import TytulDiffProducer
        TytulDiffProducer(parent=self).produce()

    def commit_tytuly(self):
        self.commit(self.diffs(Diff_Tytul_Create))
        self.commit(self.diffs(Diff_Tytul_Delete))

    def diff_funkcje(self):
        from egeria.diff_producers.nazwa_i_skrot import Funkcja_AutoraDiffProducer
        Funkcja_AutoraDiffProducer(parent=self).produce()

    def commit_funkcje(self):
        self.commit(self.diffs(Diff_Funkcja_Autora_Create))
        self.commit(self.diffs(Diff_Funkcja_Autora_Delete))

    def diff_wydzialy(self):
        from egeria.diff_producers.nazwa_i_skrot import WydzialDiffProducer
        WydzialDiffProducer(parent=self).produce()

    def commit_wydzialy(self):
        self.commit(self.diffs(Diff_Wydzial_Create))
        self.commit(self.diffs(Diff_Wydzial_Delete))

    def diff_jednostki(self):
        """
        Jednostka po nazwie
        - czy jest w bazie:
            TAK:
                - czy jest to ten sam wydział?
                    TAK: nic
                    NIE: zaktualizuj wydział,
                - czy jest widoczna i dostępna dla raportów?
                    TAK: nic
                    NIE: zaktualizuj widoczność

            NIE:
                - utwórz jednostkę, tworząc wcześniej wydział

        Sprawdź wszystkie jednostki w bazie:
        - czy jest w pliku XLS?
            TAK: nic nie rób,
            NIE: ukryj z raportów, ukryj jednostkę, ustaw wydział na "Jednostki Dawne"
            (pierwszy archiwalny wydział w bazie danych, wg kolejności ID)

        :param egeria_import:
        :return:
        """

        from egeria.diff_producers.jednostka import JednostkaDiffProducer
        JednostkaDiffProducer(parent=self).produce()

    def commit_jednostki(self):
        self.commit(self.diffs(Diff_Jednostka_Create))
        self.commit(self.diffs(Diff_Jednostka_Update))
        self.commit(self.diffs(Diff_Jednostka_Delete))



class EgeriaRow(models.Model):
    parent = models.ForeignKey(EgeriaImport)

    lp = models.IntegerField()
    tytul_stopien = models.CharField(max_length=100)
    nazwisko = models.CharField(max_length=200)
    imie = models.CharField(max_length=200)
    pesel_md5 = models.CharField(max_length=32)
    stanowisko = models.CharField(max_length=50)
    nazwa_jednostki = models.CharField(max_length=300)
    wydzial = models.CharField(max_length=150)
