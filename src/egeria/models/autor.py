# -*- encoding: utf-8 -*-

from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

from bpp.models.autor import Autor, Autor_Jednostka
from bpp.models.struktura import Jednostka


class Diff_Autor_Create(models.Model):
    nazwisko = models.CharField(max_length=200)
    imiona = models.CharField(max_length=200)
    pesel_md5 = models.CharField(max_length=32)

    jednostka = models.ForeignKey('bpp.Jednostka')
    tytul = models.ForeignKey('bpp.Tytul')
    funkcja = models.ForeignKey('bpp.Funkcja_Autora')

    def commit(self):
        autor = Autor.objects.create(
            nazwisko=self.nazwisko,
            imiona=self.imiona,
            tytul=self.tytul,
            pesel_md5=self.pesel_md5
        )

        Autor_Jednostka.objects.create(
            autor=autor,
            jednostka=self.jednostka,
            funkcja=self.funkcja,
            rozpoczal_prace=timezone.now().date(),
        )

class Diff_Autor_Update(models.Model):
    """
    Autor może mieć aktualizowany:
    * tytuł,
    * główną jednostkę, w której pracuje,
    * funkcję w głównej jednostce, w której pracuje.

    """

    reference = models.ForeignKey('bpp.Autor')

    jednostka = models.ForeignKey('bpp.Jednostka')
    tytul = models.ForeignKey('bpp.Tytul')
    funkcja = models.ForeignKey('bpp.Funkcja_Autora')

    @classmethod
    def check_if_needed(cls, elem):
        reference, jednostka, tytul, funkcja = elem['reference'], elem['jednostka'], elem['tytul'], elem['funkcja']

        if reference.tytul != tytul:
            return True

        if reference.aktualna_jednostka != jednostka:
            return True

        for elem in reference.autor_jednostka_set \
            .filter(jednostka=jednostka, zakonczyl_prace=None) \
            .exclude(rozpoczal_prace=None):
            if elem.funkcja_autora != funkcja:
                return True

    def commit(self):
        raise NotImplementedError

class Diff_Autor_Delete(models.Model):
    """
    Autor "skasowany" to autor, który:
    * jest usunięty z bazy danych (gdy nie ma żadnych odnośników do niego w bazie)
    * zakończył prace we wszystkich innych jednostkach i jest przypisany do "Obcej jednostki"
      lub do "Doktoranci" (gdy są odnośniki do niego w bazie)
    """

    reference = models.ForeignKey('bpp.Autor')

    @classmethod
    def has_links(cls, reference):
        for elem in ['wydawnictwo_ciagle', 'wydawnictwo_zwarte', 'patent']:
            if getattr(reference, elem + "_set").count() > 0:
                return True

        try:
            reference.praca_doktorska
            return True
        except ObjectDoesNotExist:
            pass

        try:
            reference.praca_habilitacyjna
            return True
        except ObjectDoesNotExist:
            pass

    @classmethod
    def check_if_needed(cls, reference):
        # Czy usunąć tego autora?
        if not cls.has_links(reference):
            # Jeżeli nie ma żadnych podlinkowanych rekordów, to tak
            return True

        if reference.aktualna_jednostka is None or reference.aktualna_jednostka.obca_jednostka != True:
            # Jeżeli hgw-gdzie-jest-przypisany, to tak
            # lub tez, jeżeli jest przypisany do innej jednostki, niż obca
            return True

    def commit(self):
        if not self.has_links(self.reference):
            self.reference.delete()
            self.delete()
            return

        # Zakończ prace we wszystkich jednostkach, w których jest rozpoczęta
        for elem in Autor_Jednostka.objects.filter(autor=self.reference, zakonczyl_prace=None)\
                .exclude(jednostka__obca_jednostka=True):
            elem.zakonczyl_prace = timezone.now().date()
            elem.save()

        for elem in Autor_Jednostka.objects.filter(autor=self.reference, jednostka__obca_jednostka=True):
            elem.rozpoczal_prace = timezone.now().date()
            elem.zakonczyl_prace = None
            elem.save()

            # Zapisz autora za pomocą metody 'Save', aby ustawić poprawnie pole "ostatnia_jednostka"
            self.reference.save()
            self.delete()
            return

        # Autor nie miał dopisanej żadnej jednostki jako "Obca jednostka", dopisz go teraz
        Autor_Jednostka.objects.create(
            autor=self.reference,
            jednostka=Jednostka.objects.filter(obca_jednostka=True).first(),
            rozpoczal_prace=timezone.now().date(),
            zakonczyl_prace=None,
        )
        # Zapisz autora za pomocą metody 'Save', aby ustawić poprawnie pole "ostatnia_jednostka"
        self.reference.save()
        self.delete()