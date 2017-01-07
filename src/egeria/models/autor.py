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
    tytul = models.ForeignKey('bpp.Tytul', blank=True, null=True)
    funkcja = models.ForeignKey('bpp.Funkcja_Autora')

    class Meta:
        abstract = True
        ordering = ('nazwisko', 'imiona', 'jednostka')


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

    class Meta:
        ordering = ('nazwisko', 'imiona', 'jednostka')

    @classmethod
    def check_if_needed(cls, parent, elem):
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

        if autor.pesel_md5 != self.pesel_md5:
            if autor.pesel_md5 is not None:
                raise Exception(
                    "Zmiana PESELu (%r %r %r %r %r; match z %r %r %r %r %r) - sprawdź poprawność procedur matchujących i "
                    "pliku importu. " % (
                        autor.nazwisko, autor.imiona, autor.tytul, autor.pesel_md5,
                        list(autor.autor_jednostka_set.all()),
                        self.nazwisko, self.imiona, self.tytul, self.pesel_md5,
                        self.jednostka))

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
                raise NotImplementedError
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

    class Meta:
        ordering = ('reference__nazwisko', 'reference__imiona', 'reference__aktualna_jednostka__nazwa')

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
    def check_if_needed(cls, parent, reference):
        """Funkcja odpowiada na pytanie, czy potrzebne jest usunięcie tego autora; jeżeli ma powiązane
        jakiekolwiek rekordy bibliograficzne to zamiast usunięcia przeprowadzone będzie dopisanie
        go do "Obcej jednostki". """
        if not cls.has_links(reference):
            # Jeżeli nie ma żadnych podlinkowanych rekordów, to tak
            return True

        if reference.aktualna_jednostka is None or reference.aktualna_jednostka != parent.uczelnia.obca_jednostka:
            # Jeżeli nie wiadomo, gdzie autor ejst przypisany - to obiekt Diff_Autor_Delete jest potrzebny,
            # żeby przypisać tego autora do Obcej Jednostki.
            #
            # Jeżeli autor jest przypisany aktualnie do innej-niż-obca jednostki - to obiekt Diff_Autor_Delete
            # jest potrzebny.
            return True

        return False

    def this_has_links(self):
        return self.has_links(self.reference)

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
