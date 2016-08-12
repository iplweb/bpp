# -*- encoding: utf-8 -*-

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

from bpp.models.autor import Autor, Autor_Jednostka
from bpp.models.struktura import Jednostka
from egeria.models.abstract import Diff_Base


class Diff_Autor_Base(Diff_Base):
    nazwisko = models.CharField(max_length=200)
    imiona = models.CharField(max_length=200)
    pesel_md5 = models.CharField(max_length=32)

    jednostka = models.ForeignKey('bpp.Jednostka')
    tytul = models.ForeignKey('bpp.Tytul')
    funkcja = models.ForeignKey('bpp.Funkcja_Autora')

    class Meta:
        abstract = True


class Diff_Autor_Create(Diff_Autor_Base):
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


class Diff_Autor_Update(Diff_Autor_Base):
    """
    Autor może mieć aktualizowany:
    * tytuł,
    * główną jednostkę, w której pracuje,
    * funkcję w głównej jednostce, w której pracuje.
    * PESEL - w sytuacji, gdy nie miał wcześniej określonego
    """

    reference = models.ForeignKey('bpp.Autor')

    @classmethod
    def check_if_needed(cls, elem):
        reference, nazwisko, imiona, jednostka, tytul, funkcja, pesel_md5 = \
            elem['reference'], elem['nazwisko'], elem['imiona'], elem['jednostka'], \
            elem['tytul'], elem['funkcja'], elem['pesel_md5']

        if reference.tytul != tytul:
            return True

        if reference.aktualna_jednostka != jednostka:
            return True

        if reference.aktualna_funkcja != funkcja:
            return True

        if reference.pesel_md5 != pesel_md5:
            return True

        if reference.imiona != imiona:
            return True

        if reference.nazwisko != nazwisko:
            return True

    def commit(self):
        autor = self.reference
        needs_saving = False

        if autor.aktualna_jednostka != self.jednostka:
            # Zakończ pracę we wszystkich jednostkach
            for elem in autor.autor_jednostka_set.all():
                elem.zakonczyl_prace = timezone.now()
                elem.save()
            Autor_Jednostka.objects.create(
                autor=autor,
                jednostka=self.jednostka,
                funkcja=self.funkcja,
                rozpoczal_prace=timezone.now()
            )
            autor.refresh_from_db()

        if autor.aktualna_funkcja != self.funkcja:
            aj = Autor_Jednostka.objects.get(
                autor=autor,
                jednostka=autor.aktualna_jednostka
            )
            aj.funkcja = self.funkcja
            aj.save()
            autor.refresh_from_db()

        if autor.pesel_md5 != self.pesel_md5:
            if autor.pesel_md5 is not None:
                raise Exception("Zmiana PESELu - sprawdź poprawność oprogramowania i pliku importu. ")
            autor.pesel_md5 = self.pesel_md5
            needs_saving = True

        if autor.tytul != self.tytul:
            autor.tytul = self.tytul
            needs_saving = True

        if autor.nazwisko != self.nazwisko:
            autor.nazwisko = self.nazwisko
            needs_saving = True

        if autor.imiona != self.imiona:
            autor.imiona = self.imiona
            needs_saving = True

        if needs_saving:
            autor.save()

        self.delete()


class Diff_Autor_Delete(Diff_Base):
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
        for elem in Autor_Jednostka.objects.filter(autor=self.reference, zakonczyl_prace=None) \
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
