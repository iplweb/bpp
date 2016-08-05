# -*- encoding: utf-8 -*-
from bpp.models.autor import Tytul, Funkcja_Autora
from bpp.models.struktura import Wydzial
from egeria.models import Diff_Tytul_Create, Diff_Tytul_Delete, Diff_Funkcja_Autora_Create, Diff_Funkcja_Autora_Delete, \
    Diff_Wydzial_Create, Diff_Wydzial_Delete
from .base import BaseDiffProducer

# def diff_nazwa_i_skrot(egeria_import, nazwa_kolumny_w_egerii, klasa, nazwa_kolumny_w_klasie):
#     current_import = egeria_import.rows()
#
#     wartosci_w_xls = current_import.values(nazwa_kolumny_w_egerii).distinct()
#
#     create_obj = globals()['Diff_%s_Create' % klasa.__name__]
#     # ACTION_CREATE
#     kwargs = {nazwa_kolumny_w_egerii + "__in": klasa.objects.all().values(nazwa_kolumny_w_klasie)}
#     nowe_rekordy = wartosci_w_xls.exclude(**kwargs)
#     for elem in nowe_rekordy:
#         create_obj.objects.create(parent=egeria_import, nazwa_skrot=elem[nazwa_kolumny_w_egerii])
#
#     delete_obj = globals()['Diff_%s_Delete' % klasa.__name__]
#     # ACTION_DELETE
#     rekordy_do_usuniecia = klasa.objects.all().exclude(skrot__in=wartosci_w_xls.values(nazwa_kolumny_w_egerii))
#     for elem in rekordy_do_usuniecia:
#         if delete_obj.check_if_needed(reference=elem):
#             delete_obj.objects.create(parent=egeria_import, reference=elem)

class NazwaISkrotDiffProducer(BaseDiffProducer):
    def get_import_values(self):
        return self.parent.rows().values(self.egeria_field).distinct()

    def get_db_values(self):
        return self.db_klass.objects.all()

    def get_new_values(self):
        """Wartości z importu oprócz wartości w bazie danych
        """
        kwargs = {self.egeria_field + "__in": self.get_db_values().values(self.db_klass_field).distinct()}
        return self.get_import_values().exclude(**kwargs)

    def get_delete_values(self):
        """Wartości z bazy danych oprócz wartości z importu
        """
        kwargs = {self.db_klass_field + "__in": self.get_import_values()}
        return self.get_db_values().exclude(**kwargs)

    def create_kwargs(self, elem):
        return dict(nazwa_skrot=elem[self.egeria_field])

    def delete_kwargs(self, elem):
        return dict(reference=elem)


class TytulDiffProducer(NazwaISkrotDiffProducer):
    egeria_field = 'tytul_stopien'
    db_klass = Tytul
    db_klass_field = 'skrot'
    create_class = Diff_Tytul_Create
    delete_class = Diff_Tytul_Delete
    update_class = None


class Funkcja_AutoraDiffProducer(NazwaISkrotDiffProducer):
    egeria_field = 'stanowisko'
    db_klass = Funkcja_Autora
    db_klass_field = 'skrot'
    create_class = Diff_Funkcja_Autora_Create
    delete_class = Diff_Funkcja_Autora_Delete
    update_class = None


class WydzialDiffProducer(NazwaISkrotDiffProducer):
    egeria_field = 'wydzial'
    db_klass = Wydzial
    db_klass_field = 'nazwa'
    create_class = Diff_Wydzial_Create
    delete_class = Diff_Wydzial_Delete
    update_class = None
