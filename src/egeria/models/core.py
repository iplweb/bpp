# -*- encoding: utf-8 -*-
import os
from md5 import md5

import xlrd
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import connection
from django.db import models, transaction
from django.db.models.query_utils import Q

from bpp.models.autor import Autor
from egeria.models.autor import Diff_Autor_Create, Diff_Autor_Update, Diff_Autor_Delete
from egeria.models.funkcja_autora import Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete
from egeria.models.jednostka import Diff_Jednostka_Create, Diff_Jednostka_Delete, Diff_Jednostka_Update
from egeria.models.tytul import Diff_Tytul_Create, Diff_Tytul_Delete
from egeria.models.wydzial import Diff_Wydzial_Create, Diff_Wydzial_Delete


class AlreadyAnalyzedError(Exception):
    pass


class EgeriaImport(models.Model):
    """
    Klasa zarządzająca importem danych z systemu Egeria.

    Import odbywa się kolejno w krokach.
    Aktualny krok importu ma numer od zera wzwyż, self.analysis_level


    Po wczytaniu pliku XLS jednorazowo, na kroku importu "zero" powinno odbyć się:
    - self.analyze - wczytaj plik XLS z self.file do bazy danych, tworząc rekordy EgeriaRow

    Późniejsze ewentualne restartowanie importu nie powinno powodować powtórnego
    uruchomienia procedury self.analyze, gdyż nie ma ona związku z faktyczną zawartością
    bazy danych a jedynie pliku XLS.

    Kroki importu są to kolejno:
    - tytuły: utwórz diffy (TytulDiffProducer), commituj Tytul_Create, Tytul_Delete, zmatchuj tytuły
    - funkcje: utwórz diffy, commituj Create, Delete, zmatchuj funcje
    - wydziały: utwórz diffy, commituj Create, Delete, zmatchuj wydziały
    - jednostki: utwórz diffy, commituj Create, *Update*, Delete, zmatchuj jednostki
    - zmatchuj autorów
    - autorzy: utwórz diffy, commituj Create, *Update*, Delete

    Matchowanie to dopisanie ID istniejących rekordów w bazie danych
    do konkretnych pól w obiektach EgeriaRow, czyli jest to np.
    dopisanie ID istniejacego w bazie danych autora do danego obiektu. Pozwala
    to potem określić np. które obiekty są nowe i które obiekty wymagają aktualizacji.

    """
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
        return reverse("egeria:reset_import_state", args=(self.pk,))

    def get_title(self):
        return os.path.basename(self.file.name)

    def rows(self):
        """
        :return: QuerySet obiektów EgeriaRow przypisanych do tego importu.
        """
        return EgeriaRow.objects.filter(parent=self)

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
            nazwa_jednostki = nazwa_jednostki.replace("  ", " ").replace("  ", " ")
            if wydzial.strip() == "":
                if nazwa_jednostki == "Biblioteka Główna":
                    wydzial = "Jednostki Ogólnouczelniane"
                else:
                    wydzial = "Brak wpisanego wydziału"

            if pesel_md5.strip() == "":
                continue

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

    def diffs(self, klass):
        return klass.objects.filter(parent=self)

    def commit(self, lst):
        map(lambda x: x.commit(), lst)

    def commit_objs(self, lst):
        map(lambda obj: self.commit(self.diffs(obj)), lst)

    def reset_objs(self, lst):
        map(lambda obj: self.diffs(obj).delete(), lst)

    DIFF_TYTUL = [Diff_Tytul_Create, Diff_Tytul_Delete]

    def diff_tytuly(self):
        from egeria.diff_producers.nazwa_i_skrot import TytulDiffProducer
        TytulDiffProducer(parent=self).produce()

    def commit_tytuly(self):
        self.commit_objs(self.DIFF_TYTUL)

    def reset_tytuly(self):
        self.reset_objs(self.DIFF_TYTUL)

    def diff_funkcje(self):
        from egeria.diff_producers.nazwa_i_skrot import Funkcja_AutoraDiffProducer
        Funkcja_AutoraDiffProducer(parent=self).produce()

    DIFF_FUNKCJE = [Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete]

    def commit_funkcje(self):
        self.commit_objs(self.DIFF_FUNKCJE)

    def reset_funkcje(self):
        self.reset_objs(self.DIFF_FUNKCJE)

    def diff_wydzialy(self):
        from egeria.diff_producers.nazwa_i_skrot import WydzialDiffProducer
        WydzialDiffProducer(parent=self).produce()

    DIFF_WYDZIALY = [Diff_Wydzial_Create, Diff_Wydzial_Delete]

    def commit_wydzialy(self):
        self.commit_objs(self.DIFF_WYDZIALY)

    def reset_wydzialy(self):
        self.reset_objs(self.DIFF_WYDZIALY)

    def diff_jednostki(self):
        from egeria.diff_producers.jednostka import JednostkaDiffProducer
        JednostkaDiffProducer(parent=self).produce()

    DIFF_JEDNOSTKI = [Diff_Jednostka_Create, Diff_Jednostka_Update, Diff_Jednostka_Delete]

    def commit_jednostki(self):
        self.commit_objs(self.DIFF_JEDNOSTKI)

    def reset_jednostki(self):
        self.reset_objs(self.DIFF_JEDNOSTKI)

    def match_jednostki(self):
        cursor = connection.cursor()
        cursor.execute("""
        UPDATE
          egeria_egeriarow
        SET
          matched_jednostka_id = bpp_jednostka.id
        FROM
          bpp_jednostka
        WHERE
          egeria_egeriarow.nazwa_jednostki = bpp_jednostka.nazwa AND
          egeria_egeriarow.parent_id = %s
        """, [self.pk, ])

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

        # mpasternak: poniższe NIE powinno być sprawdzane - niektóre osoby po prostu nie mają
        # tytułu, więc niech mają wpisane null:

        # W tym momencie nie powinno być żadnych nie-zmatchowanych tytułów
        # assert self.rows().filter(matched_tytul=None).count() == 0

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

    @transaction.atomic
    def match_autorzy(self, verbose=False):
        # Uwaga, PESEL nie jest numerem unikalnym i dwóch autorów może dzielić ten sam numer.

        # Na tym etapie matchowania mamy dostępne jednostki (EgeriaRow.matched_jednostka)

        for elem in self.rows():

            default_match = (
                Q(nazwisko=elem.nazwisko, imiona__startswith=elem.imie) |
                Q(nazwisko__startswith=elem.nazwisko + "-", imiona__startswith=elem.imie),)

            # Strategia 1: imię zaczyna się od, nazwisko identyczne, hash MD5 numeru PESEL identyczny
            a = Autor.objects.filter(pesel_md5=elem.pesel_md5, *default_match)

            if a.count() == 1:
                elem.matched_autor = a.first()
                elem.save()
                if verbose:
                    print "1", elem.nazwisko, elem.imie, elem.matched_autor
                continue

            if (elem.nazwisko, elem.imie) in [
                ("Nowak", "Maria"),
            ]:
                elem.unmatched_because_multiple = True
                elem.save()
                continue

            # Strategia 2: imię zaczyna się od, nazwisko identyczne i jedna z jednostek w zatrudnieniu
            a = Autor.objects.filter(*default_match)
            possible_matches = []
            for autor in a:
                if autor.autor_jednostka_set.filter(jednostka=elem.matched_jednostka).count() == 1:
                    possible_matches.append(autor)

            if len(possible_matches) == 1:
                elem.matched_autor = possible_matches[0]
                elem.save()
                if verbose:
                    print "2", elem.nazwisko, elem.imie, elem.matched_autor
                continue
            elif len(possible_matches) > 1:
                # W tym momencie mamy dwóch lub więcej autorów o tych samych nazwiskach,
                # imionach, pracujących w tych samych jednostkach - ten wiersz
                # musi zostać niezmatchowany, do późniejszego - ręcznego
                # uzgodnienia:
                elem.unmatched_because_multiple = True
                elem.save()
                continue

            # # W sytuacji gdy taki zestaw imion i nazwisk występuje w imporcie
            # # tylko raz - oraz w BPP tylko raz - możemy matchować po imieniu i nazwisku:
            if self.rows().filter(nazwisko=elem.nazwisko, imie=elem.imie).count() == 1:
                qset = Autor.objects.filter(nazwisko=elem.nazwisko, imiona=elem.imie)
                if qset.count() == 1:
                    elem.matched_autor = autor
                    elem.save()
                    if verbose:
                        print "3", elem.nazwisko, elem.imie, elem.matched_autor
                    continue

            # Dany autor pasuje do wielu i nie można określić czemu. Dodać go jako nowego?
            # na razie NIE

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
        lst = list(self.rows().values_list('matched_autor', flat=True).distinct())
        if None in lst:
            lst.remove(None)
        for autor in Autor.objects.all().exclude(pk__in=lst).exclude(aktualna_jednostka__obca_jednostka=True):
            if Diff_Autor_Delete.check_if_needed(autor):
                Diff_Autor_Delete.objects.create(parent=self, reference=autor)

    DIFF_AUTOR = [Diff_Autor_Create, Diff_Autor_Update, Diff_Autor_Delete]

    def commit_autorzy(self):
        self.commit_objs(self.DIFF_AUTOR)

    def reset_autorzy(self):
        self.reset_objs(self.DIFF_AUTOR)

    def cleanup(self):
        self.rows().delete()
        # os.unlink(self.file.path)
        self.delete()

    @transaction.atomic
    def reset_import_steps(self):
        """
        W sytuacji, gdy mamy zanalizowany plik w bazie danych: XLS został zanalizowany,
        rekordy EgeriaRow utworzone i jesteśmy na którymśtam etapie wrzucania diff-ów,
        baza danych może zostac sobie zwyczajnie zmieniona.

        Potrzebne wówczas będzie zresetowanie self.analysis_level, skasowanie wszystkich
        obiektów Diff_*_* i rozpoczęcie importu od nowa. Ta funkcja zapewnia właśnie
        tą funkcjonalność.

        Przez WebUI używana jest za każdym razem, kiedy z listy plików na stronie
        "Pliki importu osób" klikniemy w jakiś plik (za pomocą celery task)
        :return:
        """
        self.reset_tytuly()
        self.reset_funkcje()
        self.reset_wydzialy()
        self.reset_jednostki()
        self.reset_autorzy()

        self.analysis_level = 0
        self.save()

    @transaction.atomic
    def next_import_step(self, return_after_match_autorzy=False):
        """Ta funkcja wywołuje kolejny krok importu. W ten sposób możemy za pomocą web ui oglądać
        kolejne fazy importowania: tytuły, funkcje, wydziały, jednostki, autorzy.
        """

        if self.analysis_level == 0:
            self.diff_tytuly()

        elif self.analysis_level == 1:
            self.commit_tytuly()
            self.match_tytuly()
            self.diff_funkcje()

        elif self.analysis_level == 2:
            self.commit_funkcje()
            self.match_funkcje()
            self.diff_wydzialy()

        elif self.analysis_level == 3:
            self.commit_wydzialy()
            self.diff_jednostki()

        elif self.analysis_level == 4:
            self.commit_jednostki()
            self.match_jednostki()
            self.match_autorzy()
            if return_after_match_autorzy is not True:
                self.diff_autorzy()

        elif self.analysis_level == 5:
            self.commit_autorzy()

        self.analysis_level += 1
        self.save()

    def everything(self, return_after_match_autorzy=False, dont_analyze=False, cleanup=True):
        """

        :param return_after_match_autorzy: powoduje powrót funkcji po etapie matchowania autorów, potrzebne do testów.
        :param dont_analyze: nie analizuj pliku - w sytuacji gdyby był już przeanalizowany, potrzebne do testów.
        :return:
        """
        if dont_analyze is not True:
            self.analyze()

        while self.analysis_level < 6:
            self.next_import_step(return_after_match_autorzy=return_after_match_autorzy)

            if (return_after_match_autorzy is True) and (self.analysis_level == 5):
                return

        if cleanup:
            self.cleanup()

    def unmatched(self):
        return EgeriaRow.objects.filter(
            parent=self,
            matched_autor=None).exclude(
            unmatched_because_new=True)


class EgeriaRow(models.Model):
    parent = models.ForeignKey(EgeriaImport)

    lp = models.IntegerField()
    tytul_stopien = models.CharField(max_length=100)
    nazwisko = models.CharField(max_length=200)
    imie = models.CharField(max_length=200)
    pesel_md5 = models.CharField(max_length=32)
    stanowisko = models.CharField(max_length=250)
    nazwa_jednostki = models.CharField(max_length=300)
    wydzial = models.CharField(max_length=150)

    matched_jednostka = models.ForeignKey('bpp.Jednostka', null=True)
    matched_autor = models.ForeignKey('bpp.Autor', null=True)
    matched_tytul = models.ForeignKey('bpp.Tytul', null=True)
    matched_funkcja = models.ForeignKey('bpp.Funkcja_Autora', null=True)

    unmatched_because_new = models.BooleanField(default=False)
    unmatched_because_multiple = models.BooleanField(default=False)
