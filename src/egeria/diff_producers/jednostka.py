# -*- encoding: utf-8 -*-
from bpp.models.struktura import Jednostka, Wydzial
from egeria.models.jednostka import Diff_Jednostka_Create, Diff_Jednostka_Delete, Diff_Jednostka_Update
from .base import BaseDiffProducer

class JednostkaDiffProducer(BaseDiffProducer):
    """
    Jednostka po nazwie
    - czy jest w bazie:
        TAK:
            - czy jest to ten sam wydział?
                TAK: nic
                NIE: zaktualizuj wydział,
            - czy jest widoczna i dostępna dla raportów?
                TAK: nic
                NIE: zaktualizuj widoczność

        NIE:
            - utwórz jednostkę, tworząc wcześniej wydział

    Sprawdź wszystkie jednostki w bazie:
    - czy jest w pliku XLS?
        TAK: nic nie rób,
        NIE: ukryj z raportów, ukryj jednostkę, ustaw wydział na "Jednostki Dawne"
        (pierwszy archiwalny wydział w bazie danych, wg kolejności ID)

    :param egeria_import:
    :return:
    """

    create_class = Diff_Jednostka_Create
    update_class = Diff_Jednostka_Update
    delete_class = Diff_Jednostka_Delete

    def get_import_values(self):
        return self.parent.rows().values('nazwa_jednostki', 'wydzial').distinct()

    def get_db_values(self):
        return Jednostka.objects.all()

    def get_new_values(self):
        """Wartości z importu oprócz wartości w bazie danych
        """
        import_values = self.get_import_values()
        db_values = dict([(ref.nazwa.strip(), ref) for ref in self.get_db_values()])
        for elem in import_values:
            if elem['nazwa_jednostki'] not in db_values:
                # Nowa jednostka
                yield elem

    def get_update_values(self):
        """Wartości z importu oprócz wartości w bazie danych
        """
        import_values = self.get_import_values()
        db_values = dict([(ref.nazwa, ref) for ref in self.get_db_values()])
        for elem in import_values:
            if elem['nazwa_jednostki'] in db_values:
                jednostka = db_values[elem['nazwa_jednostki']]
                if elem['wydzial'] != jednostka.wydzial.nazwa:
                    yield dict(reference=jednostka, wydzial=Wydzial.objects.get(nazwa=elem['wydzial']))

    def get_delete_values(self):
        """Wartości z bazy danych oprócz wartości z importu
        """
        for elem in Jednostka.objects.all()\
                .exclude(wirtualna=True)\
                .exclude(nazwa__in=self.get_import_values().values_list("nazwa_jednostki", flat=True)):
            if elem.wydzial.archiwalny is False and elem.nie_archiwizuj != True:
                # Zwróc wszystkie jednostki nie występujące w pliku importu, które to
                # nie są w wydziale oznaczonym jako "Archiwalny".
                yield elem

    def create_kwargs(self, elem):
        return dict(nazwa=elem['nazwa_jednostki'], wydzial=Wydzial.objects.get(nazwa=elem['wydzial']))

    def update_kwargs(self, elem):
        return elem

    def delete_kwargs(self, elem):
        return dict(reference=elem)