# -*- encoding: utf-8 -*-


class BaseDiffProducer:
    """
    Bazowa klasa dla DiffProducerów, czyli obiektów zajmujacych tworzeniem się Diffów
    w bazie na podstawie listy wierszy EgeriaImport.rows()

    Diff w bazie to obiekt typu Diff_Create, Diff_Delete, Diff_Update - informacja
    o planowanej zmianie do wprowadzenia do bazy danych. Taki obiekt następnie prezentowany
    jest użytkownikowi WWW na web UI, do ewentualnego zaakceptowania. Gdy zaakceptowany,
    za pomocą metody Diff.commit() jest wprowadzany do bazy danych.

    DiffProducery produkują obiekty Diff dla klas typu Tytul, Jednostka, Wydzial, Funkcja_Autora,
    Autor...
    """

    def __init__(self, parent):
        self.parent = parent

    def get_import_values(self):
        """
        Zwraca listę unikalnych wartości (pojedynczych, krotek, słowników) zawartych
        w imporcie self.parent.rows()
        :return:
        """
        raise NotImplementedError

    def get_db_values(self):
        """
        Zwraca listę obecnych wartości w bazie danych.
        :return:
        """
        raise NotImplementedError

    def get_create_values(self):
        """
        Zwraca listę wartości z importu, które powinny zostać dodane
        :return:
        """
        raise NotImplementedError

    def get_update_values(self):
        """
        Zwraca listę krotek

            (reference, [lista wartości]),

        gdzie 'reference' to odnośnik do obecnego obiektu w bazie danych,
        zaś lista wartości to lista wartości które użyte powinny być do
        zaktualizowania tego obiektu.

        :return:
        """
        raise NotImplementedError

    def get_delete_values(self):
        """
        Zwraca listę referencji do obiektów w bazie danych, które powinny
        zostać skasowane.

        :return:
        """
        raise NotImplemented

    def create_kwargs(self, elem):
        raise NotImplementedError

    def update_kwargs(self, elem):
        raise NotImplementedError

    def delete_kwargs(self, elem):
        raise NotImplementedError

    def create_handler(self):
        for elem in self.get_new_values():
            kwargs = self.create_kwargs(elem)
            kwargs['parent'] = self.parent
            self.create_class.objects.create(**kwargs)

    def update_handler(self):
        for elem in self.get_update_values():
            kwargs = self.update_kwargs(elem)
            kwargs['parent'] = self.parent
            if self.update_class.check_if_needed(self.parent, elem):
                self.update_class.objects.create(**kwargs)

    def delete_handler(self):
        for elem in self.get_delete_values():
            kwargs = self.delete_kwargs(elem)
            kwargs['parent'] = self.parent
            if self.delete_class.check_if_needed(self.parent, elem):
                self.delete_class.objects.create(**kwargs)

    def produce(self):
        self.create_handler()
        if self.update_class:
            self.update_handler()
        self.delete_handler()

