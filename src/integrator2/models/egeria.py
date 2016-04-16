# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

import md5
import random

from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.db import transaction

from bpp.models.struktura import Wydzial, Uczelnia
from integrator2.models.base import BaseIntegrationElement
from integrator2.util import read_xls_data
from .base import BaseIntegration


def zrob_skrot(input):
    return "".join(item[0] for item in input.split())


class UtworzWydzial(models.Model):
    """Jeżeli w pliku importu jest wydział o takiej nazwie, której jeszcze nie ma w bazie danych.
    """
    parent = models.ForeignKey("EgeriaImportIntegration")
    uczelnia = models.ForeignKey("bpp.Uczelnia", blank=True, null=True, db_index=False)
    nazwa = models.TextField()

    # Gdy ta akcja zostaje uruchomiona, to nowo utworzony wydział idzie sobie do tego pola:
    wydzial = models.ForeignKey("bpp.Wydzial", blank=True, null=True, db_index=False)

    def needed(self):
        return Wydzial.objects.filter(nazwa=self.nazwa).count() < 1

    def perform(self):
        if self.uczelnia is None:
            u = Uczelnia.objects.all()

            if u.count() == 1:
                self.uczelnia = u[0]

            if u.count() == 0:
                self.uczelnia = Uczelnia.objects.create(
                    nazwa="Uczelnia Domyślna",
                    skrot="UD"
                )

        skrot = zrob_skrot(self.nazwa)
        while Wydzial.objects.filter(skrot=skrot).count() > 0:
            skrot += random.choice("1234567890abcedf")

        return Wydzial.objects.create(uczelnia=self.uczelnia,
                               nazwa=self.nazwa,
                               skrot=skrot)

    def get_wydzial(self):
        if self.needed():
            self.wydzial = self.perform()
            self.save()
        return self.wydzial



class ZaktualizujWydzial(models.Model):
    """Jeżeli w pliku importu jest wydział o takiej nazwie, która jest w bazie danych, to ustaw go jako
    'widoczny'."""

    parent = models.ForeignKey("EgeriaImportIntegration")
    wydzial = models.ForeignKey("bpp.Wydzial")

    def needed(self):
        return not self.wydzial.widoczny or not self.wydzial.zezwalaj_na_ranking_autorow

    def perform(self):
        self.wydzial.widoczny = True
        self.wydzial.zezwalaj_na_ranking_autorow = True
        self.wydzial.save()

    def get_wydzial(self):
        return self.wydzial


class UsunWydzial(models.Model):
    """Jeżeli w pliku nie ma danego wydziału, to usuń go - w tym przypadku, nie tyle skasuj z bazy danych,
    co zaznacz jako niewidoczny. """

    parent = models.ForeignKey("EgeriaImportIntegration")
    wydzial = models.ForeignKey("bpp.Wydzial")

    def needed(self):
        return self.wydzial.widoczny or self.wydzial.zezwalaj_na_ranking_autorow

    def perform(self):
        self.wydzial.widoczny = False
        self.wydzial.zezwalaj_na_ranking_autorow = False
        self.wydzial.save()

    def get_wydzial(self):
        return self.wydzial

class UtworzJednostke(models.Model):
    parent = models.ForeignKey("EgeriaImportIntegration")
    nazwa_wydzialu = models.TextField()
    nazwa = models.TextField()

    # def needed(self):
    #     if Jednostka.objects.filter(nazwa=self.nazwa).count()
    #
    # def perform(self):


class EgeriaImportElement(BaseIntegrationElement):
    parent = models.ForeignKey("EgeriaImportIntegration")

    sheet_name = models.CharField(max_length=50)
    lp = models.IntegerField()
    tytul_stopien = models.CharField(max_length=200)
    nazwisko = models.CharField(max_length=200)
    imie = models.CharField(max_length=200)
    pesel_md5 = models.CharField(max_length=32)
    stanowisko = models.CharField(max_length=200)
    nazwa_jednostki = models.CharField(max_length=512)
    nazwa_wydzialu = models.CharField(max_length=512)

    autor_id = models.ForeignKey("bpp.Autor", null=True, blank=True)
    jednostka_id = models.ForeignKey("bpp.Jednostka", null=True, blank=True)
    wydzial_id = models.ForeignKey("bpp.Wydzial", null=True, blank=True)

    class Meta:
        ordering = ['sheet_name', 'lp', ]

    def __iter__(self):
        return iter([
            self.sheet_name,
            self.lp,
            self.tytul_stopien,
            self.nazwisko,
            self.imie,
            self.stanowisko,
            self.nazwa_jednostki,
            self.nazwa_wydzialu
        ])

        # TODO procedury 'wynajdujące' jednostkę, wydział, autora
        # - identyfikacja wydziału:
        #       po nazwie -> jak jest JEDEN to ok,
        #       nie ma takiej nazwy -> NOWY WYDZIAŁ
        #
        # - identyfikacja jednostki:
        #       po nazwie i wydziale -> jak jest JEDNA to ok,
        #       po nazwie -> jak jest JEDNA to ok,
        #           -> czy zmieniła wydział?
        #       nie ma takiej nazwy -> nowa JEDNOSTKA
        #
        #
        # - identyfikacja autora:
        #       po PESEL_MD5 -> jak jest JEDEN to ok,
        #           - czy zmiana imienia, nazwiska lub tytułu?
        #       po nazwisku i imieniu i PESEL_MD5 -> jak jest JEDEN to ok,
        #           - czy zmiana imienia, nazwiska lub tytułu?
        #       po nazwisku i imieniu -> jak jest JEDEN to ok,
        #           - czy zmiana tytułu?
        #       jeżeli nie to NOWY AUTOR
        #           - wpisz mu MD5 PESELu
        #
        # - po wszystkim:
        #       - czy autor w bazie ma przypisaną tą jednostkę, którą ma w pliku?
        #           - jeżeli nie to przypisz nową, zakończ pracę w starej, rozpocznij w nowej
        #
        # Po imporcie ABSOLUTNIE WSZYSTKIEGO:
        #   - wszystkie WYDZIAŁY których nie ma w pliku? przestają być wyświetlane?
        #   - wszystkie jednostki których nie ma w pliku idą do "Jednostki Dawne", przestają być wyświetlane
        #   - wszyscy AUTORZY których nie ma w pliku:
        #       - mają być przypisani do "Obca jednsotka" lub "Studenci"
        #       - jeżeli są przypisani do dowolnej z nich to wstaw datę


def today():
    from datetime import datetime
    return datetime.now().date()


class EgeriaImportIntegration(BaseIntegration):
    date = models.DateField("Data", default=today, help_text="Data wygenerowania danych w systemie Egeria")

    klass = EgeriaImportElement

    class Meta:
        verbose_name = "integracja danych z Egeria"
        ordering = ['-uploaded_on']

    def input_file_to_dict_stream(self, limit=None, limit_sheets=None):
        gen = read_xls_data(
            self.file.path,
            column_mapping={
                "LP": "lp",
                "Tytuł/Stopień": "tytul_stopien",
                "NAZWISKO": "nazwisko",
                "IMIĘ": "imie",
                "PESEL": "pesel_md5",
                "Stanowisko": "stanowisko",
                "NAZWA JEDNOSTKI": "nazwa_jednostki",
                "Wydział": "nazwa_wydzialu",
            },
            transformations={
                "PESEL": lambda pesel: md5.md5(pesel).hexdigest
            },
            header_row_name="Lp",
            ignored_sheet_names=['zbiorczy'],
            limit=limit,
            limit_sheets=limit_sheets,
        )
        return gen

    def header_columns(self):
        return [
            "Arkusz",
            "LP",
            "Tytuł/Stopień",
            "Nazwisko",
            "Imię",
            "Stanowisko",
            "Nazwa jednostki",
            "Nazwa wydziału"
        ]

    def dict_stream_to_db(self, dict_stream=None, limit=None):
        if dict_stream is None:
            dict_stream = self.input_file_to_dict_stream(limit=limit)

        for elem in dict_stream:
            EgeriaImportElement.objects.create(
                parent=self,
                **dict([(str(x), y) for x, y in elem.items() if x is not None and x != "__sheet__"]))
        pass

    def match_single_record(self, elem):
        raise NotImplementedError

    def analizuj_wydzialy(self):
        # Sprawdź, czy wszystkie wydziały istnieją:
        for nazwa_wydzialu in self.records().values_list('nazwa_wydzialu', flat=True).distinct():
            w = Wydzial.objects.filter(nazwa=nazwa_wydzialu)
            cnt = w.count()

            if cnt == 0:
                UtworzWydzial.objects.get_or_create(parent=self, nazwa=nazwa_wydzialu)
            elif cnt == 1:
                ZaktualizujWydzial.objects.get_or_create(parent=self, wydzial=w[0])
            else:
                raise Exception("This should never happen")

        # Sprawdź nazwy wydziałów w bazie, które NIE występują w pliku
        for w in Wydzial.objects.all().exclude(
                nazwa__in=self.records().values_list('nazwa_wydzialu', flat=True).distinct()):
            UsunWydzial.objects.get_or_create(parent=self, wydzial=w)

    @transaction.atomic
    def match_records(self):
        self.analizuj_wydzialy()
        return super(EgeriaImportIntegration, self).match_records()

    def integrate_single_record(self, elem):
        raise NotImplementedError

    @transaction.atomic
    def integrate(self):
        raise NotImplementedError
