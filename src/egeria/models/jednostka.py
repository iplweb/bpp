# -*- encoding: utf-8 -*-

from django.db import models
from egeria.models.abstract import Diff_Delete, Diff_Base
from bpp.models import Wydzial, Jednostka
from .util import zrob_skrot


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
        raportów lub też jest w innym wydziale, niż wydział oznaczony jako archiwalny?

        Jeżeli tak, to utworzenie obiektu kasowania tej jednostki JEST potrzebne.

        :param reference:
        :return:
        """

        if reference.widoczna or reference.wchodzi_do_raportow:
            return True

        if reference.wydzial.archiwalny == False:
            return True

        return False

    def commit(self):
        """
        Jeżeli żadne rekordy autorów lub publikacji nie wskazują na tą jednostkę,
        to może zostać fizycznie usunięta z bazy danych;

        jeżeli jednak jakieś wskazują, ma być oznaczona jako niewidoczna, niedostępna
        dla raportów, oraz przeniesiona do pierwszego wydziału w bazie danych oznaczonego
        jako 'archiwalny' (issue #447)

        :return:
        """

        # Sprawdź, czy na tą jednostkę wskazują jakiekolwiek inne rekordy w bazie
        # danych:
        r = self.reference

        linked_sets = [x for x in dir(r)
                       if x.find("_set") > 0
                       and x.find("_view") == -1
                       and not x.startswith("__")
                       and not x.startswith("diff_")
                       and not x.startswith("autorzy")]

        has_linked = False
        for elem in linked_sets:
            if getattr(r, elem).count():
                has_linked = True

        if has_linked:
            r.widoczna = r.wchodzi_do_raportow = False
            archiwalny = Wydzial.objects.filter(archiwalny=True).order_by("pk").first()
            if archiwalny:
                r.wydzial = archiwalny
            r.save()
            return

        r.delete()
        self.delete()

