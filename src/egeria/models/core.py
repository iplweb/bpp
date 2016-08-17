# -*- encoding: utf-8 -*-
import os
from md5 import md5
import xlrd
from django.core.urlresolvers import reverse
from django.db import models
from django.conf import settings

from bpp.models.autor import Autor
from egeria.models.autor import Diff_Autor_Create, Diff_Autor_Update, Diff_Autor_Delete
from egeria.models.funkcja_autora import Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete
from egeria.models.jednostka import Diff_Jednostka_Create, Diff_Jednostka_Delete, Diff_Jednostka_Update
from egeria.models.tytul import Diff_Tytul_Create, Diff_Tytul_Delete
from egeria.models.wydzial import Diff_Wydzial_Create, Diff_Wydzial_Delete
from django.db import connection

class AlreadyAnalyzedError(Exception):
    pass


class EgeriaImport(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True)
    file = models.FileField("Plik XLS", upload_to="egeria_xls")

    analyzed = models.BooleanField(default=False)

    # Dla web ui:
    analysis_level = models.IntegerField(default=0)
    error = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)


    class Meta:
        ordering = ('-created_on',)

    def get_absolute_url(self):
        return reverse("egeria:detail", args=(self.pk, ))

    def get_title(self):
        return os.path.basename(self.file.name)

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
                tytul_stopien=tytul_stopien.strip().lower(),
                nazwisko=nazwisko.strip(),
                imie=imie.strip(),
                pesel_md5=md5(pesel_md5).hexdigest(),
                stanowisko=stanowisko.strip().lower(),
                nazwa_jednostki=nazwa_jednostki.strip(),
                wydzial=wydzial.strip()
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
        from egeria.diff_producers.jednostka import JednostkaDiffProducer
        JednostkaDiffProducer(parent=self).produce()

    def commit_jednostki(self):
        self.commit(self.diffs(Diff_Jednostka_Create))
        self.commit(self.diffs(Diff_Jednostka_Update))
        self.commit(self.diffs(Diff_Jednostka_Delete))

    def match_jednostki(self):
        cursor = connection.cursor()
        cursor.execute("""
        UPDATE
          egeria_egeriarow
        SET
          matched_jednostka_id = bpp_jednostka.id
        FROM
          bpp_jednostka, bpp_wydzial
        WHERE
          bpp_wydzial.id = bpp_jednostka.wydzial_id AND
          egeria_egeriarow.nazwa_jednostki = bpp_jednostka.nazwa AND
          egeria_egeriarow.wydzial = bpp_wydzial.nazwa AND
          egeria_egeriarow.parent_id = %s
        """, [self.pk,])

        # W tym momencie nie powinno być żadnych nie-zmatchowanych jednostek, jeżeli kolejność
        # odpalania procedur importujących została zachowana:
        assert self.rows().filter(matched_jednostka=None).count() == 0

    def match_tytuly(self):
        cursor = connection.cursor()
        cursor.execute("""
        UPDATE
          egeria_egeriarow
        SET
          matched_tytul_id = bpp_tytul.id
        FROM
          bpp_tytul
        WHERE
          bpp_tytul.skrot = egeria_egeriarow.tytul_stopien AND
          egeria_egeriarow.parent_id = %s
        """, [self.pk, ])

        # W tym momencie nie powinno być żadnych nie-zmatchowanych tytułów
        assert self.rows().filter(matched_tytul=None).count() == 0

    def match_funkcje(self):
        cursor = connection.cursor()
        cursor.execute("""
        UPDATE
          egeria_egeriarow
        SET
          matched_funkcja_id = bpp_funkcja_autora.id
        FROM
          bpp_funkcja_autora
        WHERE
          bpp_funkcja_autora.nazwa = egeria_egeriarow.stanowisko AND
          egeria_egeriarow.parent_id = %s
        """, [self.pk, ])

        # W tym momencie nie powinno być żadnych nie-zmatchowanych funkcji
        assert self.rows().filter(matched_funkcja=None).count() == 0

    def match_autorzy(self):
        # Nie matchujemy automatycznie po hashu MD5 numeru PESEL - ta wartość jest tylko
        # wartością pomocniczą, ponieważ PESEL nie jest numerem unikalnym i dwóch autorów
        # mogłoby dzielić ten sam numer.

        # Matchujemy "ręcznie", wiersz po wierszu.

        # Na tym etapie matchowania mamy dostępne jednostki (EgeriaRow.matched_jednostka)

        for elem in self.rows():
            # Strategia 0: hash MD5 numeru PESEL
            # PESELe nie są unikalne, ale być może w naszym zbiorze danych będzie tylko
            # jeden taki pesel, więc:
            a = Autor.objects.filter(pesel_md5=elem.pesel_md5)
            c = a.count()
            if c == 1:
                elem.matched_autor = a.first()
                elem.save()
                continue

            # Strategia 1: imię i nazwisko
            a = Autor.objects.filter(nazwisko=elem.nazwisko, imiona=elem.imie)
            c = a.count()
            if c == 0:
                elem.unmatched_because_new = True
                elem.save()
                continue

            if c == 1:
                elem.matched_autor = a.first()
                elem.save()
                continue

            # Strategia 2: imię i nazwisko i hash MD5 numeru PESEL
            a = Autor.objects.filter(nazwisko=elem.nazwisko, imiona=elem.imie, pesel_md5=elem.pesel_md5)
            if a.count() == 1:
                elem.matched_autor = a.first()
                elem.save()
                continue

            # Strategia 3: imię i nazwisko i jedna z jednostek w zatrudnieniu
            a = Autor.objects.filter(nazwisko=elem.nazwisko, imiona=elem.imie)
            possible_matches = []
            for autor in a:
                if autor.autor_jednostka_set.filter(jednostka=elem.matched_jednostka).count() == 1:
                    possible_matches.append(autor)

            if len(possible_matches) == 1:
                elem.matched_autor = possible_matches[0]
                elem.save()
                continue

            # Strategia 4: nie ma strategii 4. Dany autor pasuje do wielu i nie można określić.
            elem.unmatched_because_multiple = True
            elem.save()

    def diff_autorzy(self):
        # Utwórz nowych autorów
        for row in self.rows().filter(unmatched_because_new=True):
            Diff_Autor_Create.objects.create(
                parent=self,

                nazwisko=row.nazwisko,
                imiona=row.imie,
                pesel_md5=row.pesel_md5,

                jednostka=row.matched_jednostka,
                tytul=row.matched_tytul,
                funkcja=row.matched_funkcja
            )

        # Stwórz obiekty Update dla wszystkich zmatchowanych autorów 
        for row in self.rows().exclude(matched_autor=None):
            elem = dict(
                reference=row.matched_autor,

                nazwisko=row.nazwisko,
                imiona=row.imie,
                pesel_md5=row.pesel_md5,

                tytul=row.matched_tytul,
                funkcja=row.matched_funkcja,
                jednostka=row.matched_jednostka
            )
            if Diff_Autor_Update.check_if_needed(elem):
                Diff_Autor_Update.objects.create(parent=self, **elem)

        # Stwórz obiekty Delete dla wszystkich autorów, którzy 1) nie są w pliku
        # importu i 2) nie są w jednostce określonej jako "Obca"
        for autor in Autor.objects.all() \
            .exclude(pk__in=self.rows().values_list('matched_autor')) \
            .exclude(aktualna_jednostka__obca_jednostka=True):
            if Diff_Autor_Delete.check_if_needed(autor):
                Diff_Autor_Delete.objects.create(parent=self, reference=autor)

    def commit_autorzy(self):
        self.commit(self.diffs(Diff_Autor_Create))
        self.commit(self.diffs(Diff_Autor_Update))
        self.commit(self.diffs(Diff_Autor_Delete))

    def cleanup(self):
        self.rows().delete()
        # os.unlink(self.file.path)
        self.delete()

    def everything(self, return_after_match_autorzy=False, dont_analyze=False):
        if dont_analyze is not True:
            self.analyze()

        self.diff_tytuly()
        self.commit_tytuly()
        self.match_tytuly()

        self.diff_funkcje()
        self.commit_funkcje()
        self.match_funkcje()

        self.diff_wydzialy()
        self.commit_wydzialy()

        self.diff_jednostki()
        self.commit_jednostki()
        self.match_jednostki()

        self.match_autorzy()
        if return_after_match_autorzy:
            return
        self.diff_autorzy()
        self.commit_autorzy()

        self.cleanup()

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

    matched_jednostka = models.ForeignKey('bpp.Jednostka', null=True)
    matched_autor = models.ForeignKey('bpp.Autor', null=True)
    matched_tytul = models.ForeignKey('bpp.Tytul', null=True)
    matched_funkcja = models.ForeignKey('bpp.Funkcja_Autora', null=True)

    unmatched_because_new = models.BooleanField(default=False)
    unmatched_because_multiple = models.BooleanField(default=False)