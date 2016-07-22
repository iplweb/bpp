# -*- encoding: utf-8 -*-

import xlrd
from django.conf import settings
from django.db import models

from bpp.models.autor import Tytul, Funkcja_Autora
from bpp.models.struktura import Wydzial, Uczelnia, Jednostka


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


ACTION_CREATE, ACTION_UPDATE, ACTION_DELETE = range(0, 3)

STAGE_TYTUL, STAGE_WYDZIAL, STAGE_JEDNOSTKA, STAGE_AUTOR = range(0, 4)


class Diff_Base(models.Model):
    parent = models.ForeignKey(EgeriaImport)

    # opcjonalny odnośnik do wiersza, gdzie znajdują się informacje
    row = models.ForeignKey(EgeriaRow, blank=True, null=True)

    # Czy został dodany do bazy?
    commited = models.BooleanField(default=False)

    def commit(self):
        self.commited = True
        self.save()

    class Meta:
        abstract = True


class Diff_Create(Diff_Base):
    nazwa_skrot = models.CharField(max_length=512)

    def __unicode__(self):
        return self.nazwa_skrot

    def commit(self):
        self.klass.objects.create(nazwa=self.nazwa_skrot, skrot=self.nazwa_skrot)
        super(Diff_Create, self).commit()

    class Meta:
        abstract = True


class Diff_Delete(Diff_Base):
    # reference = models.ForeignKey(base_klass)

    def __unicode__(self):
        return self.reference.nazwa

    def commit(self):
        self.reference.delete()
        self.delete()

    @classmethod
    def check_if_needed(cls, reference):
        """
        Ta metoda sprawdza, czy potrzebne jest tworzenie tego rodzaju obiektu,
        odpowiada na pytanie "Czy potrzebne jest skasowanie obiektu do którego
        odnosi się 'reference'".

        powinna być wywoływana przed jego utworzeniem w oprogramowaniu importującym
        na etapie tworzenia diff'a.

        Przykładowo, możemy chcieć "skasować" wydział, który już jest oznaczony
        jako niewidoczny. W takiej sytuacji, tworzenie tego obiektu będzie zbędne.

        :return:
        """
        raise NotImplementedError

    class Meta:
        abstract = True


class Diff_Tytul_Create(Diff_Create):
    klass = Tytul


class Diff_Tytul_Delete(Diff_Delete):
    reference = models.ForeignKey(Tytul)

    @classmethod
    def check_if_needed(cls, reference):
        return reference.autor_set.count() == 0


class Diff_Funkcja_Autora_Create(Diff_Create):
    klass = Funkcja_Autora


class Diff_Funkcja_Autora_Delete(Diff_Delete):
    reference = models.ForeignKey(Funkcja_Autora)

    @classmethod
    def check_if_needed(cls, reference):
        return reference.autor_jednostka_set.count() == 0


def zrob_skrot(ciag, max_length, klasa, atrybut):
    """Robi skrót z ciągu znaków "ciąg", do maksymalnej długości max_length,

    następnie sprawdza, czy taki ciąg znaków występuje w bazie danych
    w sensie: Klasa.objects.all().value_list(atrybut, flat=True),

    jeżeli taki skrót już istnieje, to zaczyna obcinać ostatnie elementy i wstawiać tam
    cyferki.
    """

    pierwsze_litery = "".join([x[0].upper() for x in ciag.split(" ")])[:max_length]
    w_bazie_sa = klasa.objects.all().values_list(atrybut, flat=True).distinct()
    ret = pierwsze_litery

    a = 0
    while ret in w_bazie_sa:
        a += 1
        cyfra = str(a)
        ret = pierwsze_litery[:max_length - len(cyfra)] + cyfra

    return ret


class Diff_Wydzial_Create(Diff_Create):
    klass = Wydzial

    def commit(self):
        uczelnia = Uczelnia.objects.all().first()
        if uczelnia is None:
            uczelnia = Uczelnia.objects.create(nazwa="Uczelnia", skrot="U")
        self.klass.objects.create(
            nazwa=self.nazwa_skrot,
            skrot=zrob_skrot(self.nazwa_skrot, max_length=4, klasa=Wydzial, atrybut='skrot'),
            uczelnia=uczelnia)
        super(Diff_Create, self).commit()


class Diff_Wydzial_Delete(Diff_Delete):
    reference = models.ForeignKey(Wydzial)

    @classmethod
    def check_if_needed(cls, reference):
        if reference.jednostka_set.count() == 0:
            return True

        if reference.widoczny == False and reference.zezwalaj_na_ranking_autorow == False:
            return False

        return True

    def commit(self):
        # Jeżeli ma jakiekolwiek jednostki w sobie, to zaznacz jako niewidoczny.
        if self.reference.jednostka_set.count() == 0:
            super(Diff_Wydzial_Delete, self).commit()
        else:
            self.reference.widoczny = False
            self.reference.zezwalaj_na_ranking_autorow = False
            self.reference.save()


class Diff_Jednostka_Create(Diff_Base):
    nazwa = models.CharField(max_length=512)
    wydzial = models.ForeignKey(Wydzial)

    def commit(self):
        Jednostka.objects.create(
            wydzial=self.wydzial,
            nazwa=self.nazwa,
            skrot=zrob_skrot(self.nazwa, 128, Jednostka, 'skrot')
        )
        super(Diff_Jednostka_Create, self).commit()


class Diff_Jednostka_Update(Diff_Base):
    reference = models.ForeignKey(Jednostka)
    wydzial = models.ForeignKey(Wydzial)

    @classmethod
    def check_if_needed(cls, reference, wydzial):
        """
        - czy jest to ten sam wydział?
            TAK: nic
            NIE: zaktualizuj wydział,
        - czy jest widoczna i dostępna dla raportów?
            TAK: nic
            NIE: zaktualizuj widoczność
        """
        ret = False
        if reference.wydzial != wydzial:
            ret = True

        if reference.widoczna != True or reference.wchodzi_do_raportow != True:
            ret = True

        return ret

    def commit(self):
        self.reference.widoczna = True
        self.reference.wchodzi_do_raportow = True
        self.reference.wydzial = self.wydzial
        self.reference.save()


class Diff_Jednostka_Delete(Diff_Delete):
    reference = models.ForeignKey(Jednostka)

    @classmethod
    def check_if_needed(cls, reference):
        """

        Czy jednostka podana w parametrze 'reference' jest widoczna, dostępna do
        raportów lub też jest w innym wydziale, niż wydział oznaczony jako archiwalny.

        :param reference:
        :return:
        """
        raise NotImplementedError

    def commit(self):
        """
        Jeżeli żadne rekordy autorów lub publikacji nie wskazują na tą jednostkę,
        to może zostać fizycznie usunięta z bazy danych;

        jeżeli jednak jakieś wskazują, ma być oznaczona jako niewidoczna, niedostępna
        dla raportów, oraz przeniesiona do pierwszego wydziału w bazie danych oznaczonego
        jako 'archiwalny' (issue #447)

        :return:
        """
        raise NotImplementedError
