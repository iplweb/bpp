# -*- encoding: utf-8 -*-
from bpp.models.struktura import Jednostka
from .base import BaseDiffProducer

class JednostkaDiffProducer(BaseDiffProducer):
    def get_import_values(self):
        return self.parent.rows().values('nazwa_jednostki', 'wydzial').distinct()

    def get_db_values(self):
        return Jednostka.objects.all()

    def get_new_values(self):
        """Wartości z importu oprócz wartości w bazie danych
        """

        # TU SKONCZYLEM
        raise NotImplementedError
        raise NotImplementedError
        raise NotImplementedError
        raise NotImplementedError
        raise NotImplementedError
        raise NotImplementedError

        import_values = self.get_import_values()
        db_values = dict([(ref.nazwa_jednostki, ref) for ref in self.get_db_values()])

        for elem in import_values:
            if elem['nazwa_jednostki']
            if nazwa_jednostki not in
            if (nazwa_jednostki, wydzial) in import_values:
                raise NotImplementedError
                raise NotImplementedError
                raise NotImplementedError
                raise NotImplementedError
                raise NotImplementedError


                # XXX TU SKONCZYLEM
                pass

        # TU SKONCZYLEM
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
