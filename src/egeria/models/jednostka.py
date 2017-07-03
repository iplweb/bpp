# -*- encoding: utf-8 -*-
from datetime import date, timedelta

from django.db import models, transaction

from bpp.models import Wydzial, Jednostka
from bpp.models.struktura import Jednostka_Wydzial
from egeria.models.abstract import Diff_Delete, Diff_Base
from egeria.models.util import date_range_inside
from .util import zrob_skrot
from django.utils import six

@six.python_2_unicode_compatible
class Diff_Jednostka_Create(Diff_Base):
    nazwa = models.CharField(max_length=512)
    wydzial = models.ForeignKey(Wydzial)

    def __str__(self):
        return " ".join([self.nazwa, "-", self.wydzial.nazwa])

    def commit(self):
        j = Jednostka.objects.create(
            uczelnia_id=self.parent.uczelnia_id,
            wydzial_id=self.wydzial_id,
            nazwa=self.nazwa,
            skrot=zrob_skrot(self.nazwa, 128, Jednostka, 'skrot')
        )
        Jednostka_Wydzial.objects.create(
            jednostka_id=j.pk,
            wydzial_id=self.wydzial_id,
            od=self.parent.od,
            do=self.parent.do
        )
        super(Diff_Jednostka_Create, self).commit()


class Diff_Jednostka_Update(Diff_Base):
    reference = models.ForeignKey(Jednostka)
    wydzial = models.ForeignKey(Wydzial)

    def visibility_changed(self):
        if self.reference.widoczna != True or self.reference.wchodzi_do_raportow != True:
            return True

    @classmethod
    def check_if_needed(cls, parent, elem):
        """
        - czy w okresie czasu parent(od, do) jednostka ma przypisany self.wydzial?
            TAK: nic
            NIE: jest potrzebne dopisanie tego wydziału
        - czy jest widoczna i dostępna dla raportów?
            TAK: nic
            NIE: jest potrezbna zmiana
        """
        reference = elem['reference']
        wydzial = elem['wydzial']
        ret = False

        q = reference.przypisania_dla_czasokresu(parent.od, parent.do).order_by("-od_not_null")

        if q.count() > 1:
            # W tym czasokresie jest więcej, niż jedno przypisanie. W pliku importu za dany okres
            # przypisanie jest ZAWSZE jedno. Zatem, wymagana jest aktualizacja
            ret = True
        elif q.count() == 1:
            # Czy czasokres (parent.od, parent.do) jest cały wewnątrz zwracanego
            # czasokresu obiektu Jednostka_Wydzial? Mimo nazwy "parent", nadrzędnym
            # obiektem w tym kontekście jest Jednostka_Wydział, który swoim zakresem
            # musi "objąć" zakres importowanych danych. Jeżeli go nie obejmie, to wymagana
            # jest aktualizacja, czyli funkcja check_if_needed ma zwrócić True.

            jw = q.first()
            if not date_range_inside(jw.od, jw.do, parent.od, parent.do):
                ret = True
            if jw.wydzial_id != wydzial.pk:
                ret = True
        else:
            # q.count() == 0
            # Dodaj przypisanie
            ret = True

        if reference.widoczna != True or reference.wchodzi_do_raportow != True:
            ret = True

        return ret

    @transaction.atomic
    def commit(self):
        jednostka = self.reference
        jednostka.widoczna = jednostka.wchodzi_do_raportow = True
        jednostka.save()

        # Przypisz do wydziału zdefiniowanego w pliku dla czasokresu parent.od, parent.do
        Jednostka_Wydzial.objects.wyczysc_przypisania(
            jednostka=jednostka,
            parent_od=self.parent.od,
            parent_do=self.parent.do
        )

        Jednostka_Wydzial.objects.create(
            jednostka=jednostka,
            wydzial=self.wydzial,
            od=self.parent.od,
            do=self.parent.do
        )

        super(Diff_Jednostka_Update, self).commit()


class Diff_Jednostka_Delete(Diff_Delete):
    reference = models.ForeignKey(Jednostka)

    @classmethod
    def check_if_needed(cls, parent, reference):
        """
        Czy jednostka podana w parametrze 'reference' jest widoczna, dostępna do
        raportów lub też jest w innym wydziale, niż wydział oznaczony jako archiwalny?

        Jeżeli tak, to utworzenie obiektu kasowania tej jednostki JEST potrzebne.

        :param reference:
        :return:
        """

        if not reference.zarzadzaj_automatycznie:
            return False

        if reference.wydzial is not None and not reference.wydzial.zarzadzaj_automatycznie:
            return False

        if reference.widoczna or reference.wchodzi_do_raportow or reference.aktualna:
            return True

        return False

    def has_linked(self):
        r = self.reference

        linked_sets = [x for x in dir(r)
                       if x.find("_set") > 0
                       and x.find("_view") == -1
                       and not x.startswith("jednostka_wydzial_set")
                       and not x.startswith("__")
                       and not x.startswith("diff_")
                       and not x.startswith("autorzy")]

        has_linked = False
        for elem in linked_sets:
            if getattr(r, elem).count():
                has_linked = True

        return has_linked

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
        jednostka = self.reference

        if self.has_linked():
            jednostka.widoczna = jednostka.wchodzi_do_raportow = False
            jednostka.save()
            Jednostka_Wydzial.objects.wyczysc_przypisania(jednostka, self.parent.od, self.parent.do)
            return

        jednostka.delete()
        self.delete()

    def will_really_delete(self):
        if self.has_linked():
            return False
        return True
